from __future__ import annotations

import argparse
import json
import os
from email.utils import parsedate_to_datetime
from pathlib import Path

from collector.cli import load_sources
from collector.cloud_store import DriveBigQueryStore
from collector.conab_armazens import SOURCE_ID, parse_conab_armazens
from collector.conab_armazens_bigquery import ConabArmazensBigQueryLoader
from collector.orchestrator import COLLECTOR_VERSION, CollectorEngine


def _publication_iso(last_modified: str | None) -> str | None:
    if not last_modified:
        return None
    try:
        return parsedate_to_datetime(last_modified).isoformat()
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="CONAB Armazens: RAW -> parse -> BigQuery canonico")
    parser.add_argument("--config", default="collector/config/sources.pilot.json")
    args = parser.parse_args()

    specs = load_sources(Path(args.config))
    spec = next((item for item in specs if item.source_id == SOURCE_ID), None)
    if spec is None:
        raise SystemExit(f"Fonte {SOURCE_ID!r} ausente em {args.config}")

    store = DriveBigQueryStore()
    outcome = CollectorEngine(store=store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        print(json.dumps({"acquisition": manifest.to_dict()}, ensure_ascii=False, sort_keys=True))
        return 1

    parsed = parse_conab_armazens(
        outcome.payload,
        snapshot_id=manifest.sha256,
        data_coleta=manifest.data_coleta,
        raw_artifact_ref=manifest.raw_artifact_ref,
        observed_url=manifest.observed_url,
        data_publicacao=_publication_iso(manifest.last_modified),
        collector_version=COLLECTOR_VERSION,
    )
    parse_stats = {
        "records_read": parsed.records_read,
        "records_accepted": parsed.records_accepted,
        "records_rejected": parsed.records_rejected,
        "duplicates_removed": parsed.duplicates_removed,
        "encoding": parsed.encoding,
        "delimiter": parsed.delimiter,
        "source_headers": parsed.source_headers,
        "normalized_headers": parsed.normalized_headers,
        "warnings": parsed.warnings,
    }
    if parsed.warnings:
        print(json.dumps({"status": "blocked_by_quality_gate", "parsing": parse_stats}, ensure_ascii=False, sort_keys=True))
        return 2
    if not parsed.rows:
        print(json.dumps({"status": "blocked_empty_parse", "parsing": parse_stats}, ensure_ascii=False, sort_keys=True))
        return 2

    loader = ConabArmazensBigQueryLoader(
        project_id=store.project_id,
        dataset_id=os.environ.get("AGROLOG_LOGISTICA_DATASET", "logistica"),
        ops_dataset_id=store.dataset_id,
        location=store.bq_location,
        client=store.bq,
    )
    loaded = loader.load(parsed.rows, snapshot_id=manifest.sha256, parse_stats=parse_stats)
    print(json.dumps({
        "acquisition": manifest.to_dict(),
        "parsing": parse_stats,
        "load": loaded.to_dict(),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
