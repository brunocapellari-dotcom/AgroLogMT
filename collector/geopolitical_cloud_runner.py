from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .cli import load_sources
from .cloud_store import DriveBigQueryStore
from .geopolitical import cluster_events, parse_gdelt_doc_payload, parse_ucdp_payload
from .geopolitical_bigquery import GeopoliticalBigQueryStore
from .geopolitical_reports import build_geopolitical_report, render_geopolitical_report_markdown
from .geopolitical_sources import parse_reliefweb_payload
from .orchestrator import CollectorEngine


PARSERS = {
    "gdelt_doc": parse_gdelt_doc_payload,
    "reliefweb": parse_reliefweb_payload,
    "ucdp": parse_ucdp_payload,
}


def main() -> int:
    config = os.environ.get("AGROLOG_GEOPOLITICAL_CONFIG", "/app/collector/config/sources.geopolitical.example.json")
    source_id = os.environ.get("AGROLOG_SOURCE_ID")
    min_priority = int(os.environ.get("AGROLOG_GEO_REPORT_MIN_PRIORITY", "0"))
    max_events = int(os.environ.get("AGROLOG_GEO_REPORT_MAX_EVENTS", "20"))
    max_news = int(os.environ.get("AGROLOG_GEO_REPORT_MAX_NEWS", "5"))

    specs = load_sources(Path(config))
    selected = [spec for spec in specs if spec.enabled and (not source_id or spec.source_id == source_id)]
    if not selected:
        raise SystemExit(f"Nenhuma fonte geopolitica habilitada para source_id={source_id!r}")

    raw_store = DriveBigQueryStore()
    intelligence_store = GeopoliticalBigQueryStore()
    engine = CollectorEngine(store=raw_store)  # type: ignore[arg-type]

    all_events = []
    failures = 0
    for spec in selected:
        outcome = engine.run_source_capture(spec)
        manifest = outcome.manifest
        print(json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True), flush=True)
        if manifest.status == "error":
            failures += 1
            continue
        if outcome.payload is None:
            continue
        parser_name = str(spec.options.get("parser", "")).strip()
        parser_fn = PARSERS.get(parser_name)
        if parser_fn is None:
            print(json.dumps({"source_id": spec.source_id, "warning": f"parser desconhecido: {parser_name}"}), flush=True)
            continue
        events = parser_fn(
            outcome.payload,
            source_id=spec.source_id,
            collected_at=manifest.data_coleta,
            raw_artifact_ref=manifest.raw_artifact_ref,
        )
        intelligence_store.upsert_events(events)
        all_events.extend(events)
        print(json.dumps({"source_id": spec.source_id, "events_upserted": len(events)}, ensure_ascii=False), flush=True)

    clusters = cluster_events(all_events)
    generated_at = datetime.now(timezone.utc).isoformat()
    intelligence_store.upsert_clusters(clusters, generated_at=generated_at)
    report = build_geopolitical_report(
        clusters,
        generated_at=generated_at,
        report_type="situational",
        min_priority=min_priority,
        max_events=max_events,
        max_news_per_event=max_news,
    )
    markdown = render_geopolitical_report_markdown(report)
    intelligence_store.upsert_report(report, markdown)
    print(
        json.dumps(
            {
                "clusters_upserted": len(clusters),
                "report_id": report["report_id"],
                "report_events": report["event_count"],
                "report_news": report["news_count"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
