from __future__ import annotations

import os
from typing import Any

from .cloud_store import DriveBigQueryStore
from .mapa_sigsif import SOURCE_ID, build_canonical_rows
from .mapa_sigsif_bigquery import MapaSigsifBigQueryLoader
from .models import SourceSpec
from .orchestrator import CollectorEngine


def run_mapa_sigsif_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    if spec.source_id != SOURCE_ID:
        raise ValueError(f"source_id inesperado para SIGSIF: {spec.source_id}")

    outcome = CollectorEngine(store=store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"status": "acquisition_error", "acquisition": manifest.to_dict()}

    try:
        rows, stats = build_canonical_rows(
            outcome.payload,
            source_url=str(manifest.observed_url or spec.url or ""),
            data_coleta=manifest.data_coleta,
            raw_artifact_ref=manifest.raw_artifact_ref,
            collector_version=manifest.collector_version,
        )
        if stats["total"] <= 0:
            raise RuntimeError("SIGSIF current MT cattle snapshot is empty")
        if stats["internal_reference_period_available"] is not False:
            raise RuntimeError("SIGSIF temporal semantics drifted; contract must be reviewed")
        if any(row["point_in_time_feature_eligible"] for row in rows):
            raise RuntimeError("SIGSIF temporal guard failed")

        loader = MapaSigsifBigQueryLoader(
            project_id=store.project_id,
            dataset_id=os.environ.get("AGROLOG_PECUARIA_DATASET", "pecuaria"),
            ops_dataset_id=store.dataset_id,
            location=store.bq_location,
            client=store.bq,
        )
        loaded = loader.load(rows, snapshot_id=manifest.sha256, parse_stats=stats)
        return 0, {
            "status": "ok",
            "acquisition": manifest.to_dict(),
            "parse": stats,
            "load": loaded.to_dict(),
        }
    except Exception as exc:  # noqa: BLE001
        return 2, {
            "status": "blocked_by_quality_gate",
            "acquisition": manifest.to_dict(),
            "error": f"{type(exc).__name__}: {exc}",
        }
