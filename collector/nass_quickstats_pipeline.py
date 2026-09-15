from __future__ import annotations

import json
import os
from typing import Any

from .cloud_store import DriveBigQueryStore
from .models import SourceSpec
from .nass_quickstats_bigquery import NassQuickStatsBigQueryLoader
from .nass_quickstats_normalizer import normalize_nass_rows, validate_normalized_nass_rows
from .orchestrator import CollectorEngine


def run_nass_quickstats_pipeline(
    spec: SourceSpec,
    store: DriveBigQueryStore,
) -> tuple[int, dict[str, Any]]:
    outcome = CollectorEngine(store=store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"status": "acquisition_failed", "acquisition": manifest.to_dict()}

    try:
        envelope = json.loads(outcome.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return 2, {
            "status": "blocked_by_quality_gate",
            "reason": f"nass_invalid_json:{type(exc).__name__}",
            "acquisition": manifest.to_dict(),
        }
    rows = envelope.get("data") if isinstance(envelope, dict) else None
    if not isinstance(rows, list):
        return 2, {
            "status": "blocked_by_quality_gate",
            "reason": "nass_payload_data_not_list",
            "acquisition": manifest.to_dict(),
        }
    if not rows:
        return 0, {
            "status": "no_records",
            "reason": "nass_query_returned_zero_rows",
            "acquisition": manifest.to_dict(),
        }

    normalized = normalize_nass_rows(
        rows,
        source_id=spec.source_id,
        snapshot_id=manifest.sha256,
        data_coleta=manifest.data_coleta,
        source_url=manifest.observed_url or "https://quickstats.nass.usda.gov/api",
        source_hash=manifest.sha256,
        raw_artifact_ref=manifest.raw_artifact_ref,
    )
    query = spec.options.get("query") if isinstance(spec.options.get("query"), dict) else {}
    expected_commodity = str(query.get("commodity_desc", "")).strip() or None
    expected_frequency = str(query.get("freq_desc", "")).strip() or None
    try:
        quality = validate_normalized_nass_rows(
            normalized,
            expected_source_id=spec.source_id,
            expected_commodity=expected_commodity,
            expected_frequency=expected_frequency,
        )
    except ValueError as exc:
        return 2, {
            "status": "blocked_by_quality_gate",
            "reason": str(exc),
            "acquisition": manifest.to_dict(),
        }
    if int(quality.get("duplicates", 0)):
        return 2, {
            "status": "blocked_by_quality_gate",
            "reason": f"nass_natural_key_duplicates:{quality['duplicates']}",
            "quality": quality,
            "acquisition": manifest.to_dict(),
        }

    loader = NassQuickStatsBigQueryLoader(
        project_id=store.project_id,
        dataset_id=os.environ.get("AGROLOG_AGRO_DATASET", "agro"),
        location=store.bq_location,
        client=store.bq,
    )
    loaded = loader.load(normalized, snapshot_id=manifest.sha256)
    return 0, {
        "status": "loaded" if loaded.get("status") == "loaded" else str(loaded.get("status")),
        "acquisition": manifest.to_dict(),
        "quality": quality,
        "load": loaded,
    }
