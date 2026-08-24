from __future__ import annotations

import os
from email.utils import parsedate_to_datetime
from typing import Any

from .cloud_store import DriveBigQueryStore
from .conab_armazens import parse_conab_armazens
from .conab_armazens_bigquery import ConabArmazensBigQueryLoader
from .models import SourceSpec
from .orchestrator import COLLECTOR_VERSION, CollectorEngine


def publication_iso(last_modified: str | None) -> str | None:
    if not last_modified:
        return None
    try:
        return parsedate_to_datetime(last_modified).isoformat()
    except (TypeError, ValueError):
        return None


def run_conab_armazens_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    outcome = CollectorEngine(store=store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"acquisition": manifest.to_dict()}

    parsed = parse_conab_armazens(
        outcome.payload,
        snapshot_id=manifest.sha256,
        data_coleta=manifest.data_coleta,
        raw_artifact_ref=manifest.raw_artifact_ref,
        observed_url=manifest.observed_url,
        data_publicacao=publication_iso(manifest.last_modified),
        collector_version=COLLECTOR_VERSION,
    )
    stats = {
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
    if parsed.warnings or not parsed.rows:
        return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict(), "parsing": stats}

    loader = ConabArmazensBigQueryLoader(
        project_id=store.project_id,
        dataset_id=os.environ.get("AGROLOG_LOGISTICA_DATASET", "logistica"),
        ops_dataset_id=store.dataset_id,
        location=store.bq_location,
        client=store.bq,
    )
    loaded = loader.load(parsed.rows, snapshot_id=manifest.sha256, parse_stats=stats)
    return 0, {"acquisition": manifest.to_dict(), "parsing": stats, "load": loaded.to_dict()}
