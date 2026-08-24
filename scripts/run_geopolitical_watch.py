from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from collector.cli import load_sources
from collector.geopolitical import (
    cluster_events,
    parse_gdelt_doc_payload,
    parse_ucdp_payload,
    score_cluster,
)
from collector.geopolitical_reports import build_geopolitical_report, render_geopolitical_report_markdown
from collector.geopolitical_sources import parse_reliefweb_payload
from collector.orchestrator import CollectorEngine
from collector.storage import LocalStore


PARSERS = {
    "gdelt_doc": parse_gdelt_doc_payload,
    "reliefweb": parse_reliefweb_payload,
    "ucdp": parse_ucdp_payload,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog MT - Geopolitical Watch")
    parser.add_argument(
        "--config",
        default="collector/config/sources.geopolitical.example.json",
        help="Arquivo de configuracao de fontes",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Raiz local de RAW/state/manifests/normalized/reports; AGROLOG_RAW_ROOT e o default",
    )
    parser.add_argument("--source", help="Executa somente uma fonte")
    parser.add_argument("--report-min-priority", type=int, default=0)
    parser.add_argument("--report-max-events", type=int, default=20)
    parser.add_argument("--report-max-news", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.root or os.environ.get("AGROLOG_RAW_ROOT", ".agrolog"))
    store = LocalStore(root)
    engine = CollectorEngine(store=store)
    specs = load_sources(args.config)

    exit_code = 0
    all_events = []
    for spec in specs:
        if args.source and spec.source_id != args.source:
            continue
        manifest = engine.run_source(spec)
        summary = {
            "source_id": spec.source_id,
            "status": manifest.status,
            "changed": manifest.changed,
            "error": manifest.error,
        }
        print(json.dumps(summary, ensure_ascii=False))
        if manifest.status == "error":
            exit_code = 1
            continue
        if manifest.status == "disabled" or not manifest.raw_artifact_ref:
            continue

        parser_name = str(spec.options.get("parser", "")).strip()
        parser_fn = PARSERS.get(parser_name)
        if parser_fn is None:
            continue

        raw_path = Path(manifest.raw_artifact_ref)
        payload = raw_path.read_bytes()
        events = parser_fn(
            payload,
            source_id=spec.source_id,
            collected_at=manifest.data_coleta,
            raw_artifact_ref=manifest.raw_artifact_ref,
        )
        all_events.extend(events)

        normalized_path = (
            root
            / "normalized"
            / "geopolitical"
            / spec.source_id
            / manifest.data_coleta[:10]
            / f"{manifest.sha256 or 'snapshot'}.jsonl"
        )
        normalized_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.write_text(
            "".join(json.dumps(event.to_dict(), ensure_ascii=False) + "\n" for event in events),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "source_id": spec.source_id,
                    "normalized_records": len(events),
                    "normalized_path": str(normalized_path),
                },
                ensure_ascii=False,
            )
        )

    clusters = cluster_events(all_events)
    cluster_path = root / "normalized" / "geopolitical" / "latest_clusters.jsonl"
    cluster_path.parent.mkdir(parents=True, exist_ok=True)
    cluster_path.write_text(
        "".join(
            json.dumps(
                {
                    **cluster.to_dict(),
                    "priority_score": score_cluster(cluster),
                    "priority_method_version": "geo-watch-v0.1",
                },
                ensure_ascii=False,
            )
            + "\n"
            for cluster in clusters
        ),
        encoding="utf-8",
    )
    print(json.dumps({"clusters": len(clusters), "cluster_path": str(cluster_path)}, ensure_ascii=False))

    generated_at = datetime.now(timezone.utc).isoformat()
    report = build_geopolitical_report(
        clusters,
        generated_at=generated_at,
        report_type="situational",
        min_priority=args.report_min_priority,
        max_events=args.report_max_events,
        max_news_per_event=args.report_max_news,
    )
    report_markdown = render_geopolitical_report_markdown(report)
    stamp = generated_at.replace(":", "-").replace("+", "_")
    day = generated_at[:10]
    report_dir = root / "reports" / "geopolitical" / day
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{stamp}.json"
    md_path = report_dir / f"{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(report_markdown, encoding="utf-8")

    latest_dir = root / "reports" / "geopolitical"
    latest_json = latest_dir / "latest.json"
    latest_md = latest_dir / "latest.md"
    latest_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_md.write_text(report_markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "report_id": report["report_id"],
                "report_events": report["event_count"],
                "report_news": report["news_count"],
                "report_json": str(json_path),
                "report_markdown": str(md_path),
                "latest_markdown": str(latest_md),
            },
            ensure_ascii=False,
        )
    )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
