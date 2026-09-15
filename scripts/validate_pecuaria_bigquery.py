#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any


def _one(client: Any, sql: str, params: list[Any] | None = None) -> Any:
    from google.cloud import bigquery

    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = list(client.query(sql, job_config=cfg).result())
    if not rows:
        raise RuntimeError("validation query returned no rows")
    return rows[0]


def validate_ppm(
    *,
    project_id: str,
    dataset_id: str = "pecuaria",
    ops_dataset_id: str = "agrolog_ops",
    location: str = "southamerica-east1",
    require_idempotency: bool = False,
) -> dict[str, Any]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id, location=location)
    table = f"{project_id}.{dataset_id}.ibge_ppm_cattle_mt"
    latest = f"{project_id}.{dataset_id}.v_ibge_ppm_cattle_mt_latest"
    state_view = f"{project_id}.{dataset_id}.v_ibge_ppm_cattle_mt_state_year"
    audit = f"{project_id}.{ops_dataset_id}.domain_load_runs"
    collector_runs = f"{project_id}.{ops_dataset_id}.collector_runs"

    base = _one(
        client,
        f"""
SELECT
  COUNT(*) rows_total,
  COUNT(DISTINCT record_id) record_ids,
  COUNT(DISTINCT snapshot_id) snapshots,
  MIN(year) year_min,
  MAX(year) year_max,
  COUNT(DISTINCT geo_code_ibge) municipalities,
  COUNTIF(point_in_time_feature_eligible) pit_leaks,
  COUNTIF(data_publicacao IS NOT NULL) invented_publication_rows,
  COUNTIF(data_referencia != DATE(CONCAT(CAST(year AS STRING), '-12-31'))) bad_reference_dates
FROM `{table}`
""",
    )
    if int(base["rows_total"]) <= 0:
        raise RuntimeError("PPM table is empty")
    if int(base["rows_total"]) != int(base["record_ids"]):
        raise RuntimeError("PPM duplicate record_id detected")
    if int(base["year_min"]) > 1974:
        raise RuntimeError(f"PPM history starts too late: {base['year_min']}")
    if int(base["year_max"]) < 2024:
        raise RuntimeError(f"PPM history ends too early: {base['year_max']}")
    if int(base["municipalities"]) < 100:
        raise RuntimeError(f"PPM municipality coverage too small: {base['municipalities']}")
    if int(base["pit_leaks"]) or int(base["invented_publication_rows"]) or int(base["bad_reference_dates"]):
        raise RuntimeError("PPM temporal/leakage guard failed")

    current = _one(
        client,
        f"""
SELECT
  year,
  municipios_observados,
  rebanho_bovino_cabecas,
  historical_pit_guard_preserved
FROM `{state_view}`
ORDER BY year DESC
LIMIT 1
""",
    )
    if int(current["municipios_observados"]) < 100 or float(current["rebanho_bovino_cabecas"]) <= 0:
        raise RuntimeError("PPM latest state aggregate is not material")
    if current["historical_pit_guard_preserved"] is not True:
        raise RuntimeError("PPM state view lost PIT guard")

    latest_count = _one(client, f"SELECT COUNT(*) n FROM `{latest}`")["n"]
    if int(latest_count) <= 0 or int(latest_count) > int(base["rows_total"]):
        raise RuntimeError("PPM latest view count invalid")

    source_id = "ibge_sidra_ppm_3939"
    params = [bigquery.ScalarQueryParameter("source_id", "STRING", source_id)]
    raw = _one(
        client,
        f"""
SELECT COUNT(*) runs,
       COUNTIF(STARTS_WITH(raw_artifact_ref, 'drive://')) drive_runs,
       ARRAY_AGG(sha256 IGNORE NULLS ORDER BY finished_at DESC LIMIT 1)[SAFE_OFFSET(0)] latest_sha
FROM `{collector_runs}`
WHERE source_id=@source_id AND status IN ('updated','unchanged')
""",
        params,
    )
    if int(raw["runs"]) <= 0 or int(raw["drive_runs"]) <= 0 or not raw["latest_sha"]:
        raise RuntimeError("PPM RAW/collector evidence missing")

    from google.cloud import bigquery as bq
    audit_params = [bq.ScalarQueryParameter("source_id", "STRING", source_id)]
    audit_row = _one(
        client,
        f"""
SELECT
  COUNT(*) runs,
  COUNTIF(status='loaded') loaded_runs,
  COUNTIF(status='already_loaded') idempotent_runs,
  MAX(records_inserted) max_inserted
FROM `{audit}`
WHERE source_id=@source_id
""",
        audit_params,
    )
    if int(audit_row["loaded_runs"]) <= 0 or int(audit_row["max_inserted"] or 0) <= 0:
        raise RuntimeError("PPM load audit missing")
    idempotent = int(audit_row["idempotent_runs"]) > 0
    if require_idempotency and not idempotent:
        raise RuntimeError("PPM idempotency not yet proven")

    return {
        "status": "PASS",
        "table": table,
        "latest_view": latest,
        "state_view": state_view,
        "rows": int(base["rows_total"]),
        "snapshots": int(base["snapshots"]),
        "year_min": int(base["year_min"]),
        "year_max": int(base["year_max"]),
        "municipalities": int(base["municipalities"]),
        "latest_state_year": int(current["year"]),
        "latest_state_herd": float(current["rebanho_bovino_cabecas"]),
        "raw_drive_evidence": True,
        "temporal_guard": True,
        "idempotency_proven": idempotent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production IBGE PPM cattle history in BigQuery")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="pecuaria")
    parser.add_argument("--ops-dataset", default="agrolog_ops")
    parser.add_argument("--location", default="southamerica-east1")
    parser.add_argument("--require-idempotency", action="store_true")
    args = parser.parse_args()
    try:
        report = validate_ppm(
            project_id=args.project,
            dataset_id=args.dataset,
            ops_dataset_id=args.ops_dataset,
            location=args.location,
            require_idempotency=args.require_idempotency,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
