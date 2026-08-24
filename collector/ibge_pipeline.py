from __future__ import annotations

import json
import os
from typing import Any

from .cloud_store import DriveBigQueryStore
from .geo_ibge import parse_municipalities
from .geo_ibge_bigquery import IbgeMunicipalityBigQueryLoader, municipality_rows
from .models import SourceSpec
from .orchestrator import CollectorEngine

SOURCE_ID = "ibge_municipios_mt"


def run_ibge_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    outcome = CollectorEngine(store=store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"acquisition": manifest.to_dict()}
    payload = json.loads(outcome.payload.decode("utf-8"))
    if not isinstance(payload, list):
        return 2, {"status": "blocked_by_quality_gate", "reason": "ibge_payload_not_list", "acquisition": manifest.to_dict()}
    parsed = parse_municipalities(payload)
    if not parsed:
        return 2, {"status": "blocked_by_quality_gate", "reason": "ibge_no_municipalities", "acquisition": manifest.to_dict()}
    if len({row.codigo_ibge for row in parsed}) != len(parsed):
        return 2, {"status": "blocked_by_quality_gate", "reason": "ibge_duplicate_codes", "acquisition": manifest.to_dict()}
    rows = municipality_rows(
        parsed, snapshot_id=manifest.sha256, data_coleta=manifest.data_coleta,
        source_url=manifest.observed_url or spec.url or "", source_hash=manifest.sha256,
        raw_artifact_ref=manifest.raw_artifact_ref,
    )
    loader = IbgeMunicipalityBigQueryLoader(
        project_id=store.project_id,
        dataset_id=os.environ.get("AGROLOG_REFERENCE_DATASET", "referencia"),
        location=store.bq_location,
        client=store.bq,
    )
    loaded = loader.load(rows, snapshot_id=manifest.sha256)
    return 0, {"acquisition": manifest.to_dict(), "parsed_rows": len(parsed), "load": loaded}
