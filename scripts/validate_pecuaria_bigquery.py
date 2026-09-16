#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

PPM_SOURCE_ID = "ibge_sidra_ppm_3939"
SLAUGHTER_SOURCE_ID = "ibge_sidra_slaughter_1092"
SIGSIF_SOURCE_ID = "mapa_sigsif_slaughter_snapshot"


def _one(client: Any, sql: str, params: list[Any] | None = None) -> Any:
    from google.cloud import bigquery

    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    rows = list(client.query(sql, job_config=cfg).result())
    if not rows:
        raise RuntimeError("validation query returned no rows")
    return rows[0]


def _source_evidence(
    client: Any,
    *,
    project_id: str,
    ops_dataset_id: str,
    source_id: str,
    require_idempotency: bool,
) -> dict[str, Any]:
    from google.cloud import bigquery

    collector_runs = f"{project_id}.{ops_dataset_id}.collector_runs"
    audit = f"{project_id}.{ops_dataset_id}.domain_load_runs"
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
    if int(raw["runs"] or 0) <= 0 or int(raw["drive_runs"] or 0) <= 0 or not raw["latest_sha"]:
        raise RuntimeError(f"{source_id}: RAW/collector evidence missing")

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
        params,
    )
    if int(audit_row["loaded_runs"] or 0) <= 0 or int(audit_row["max_inserted"] or 0) <= 0:
        raise RuntimeError(f"{source_id}: load audit missing")
    idempotent = int(audit_row["idempotent_runs"] or 0) > 0
    if require_idempotency and not idempotent:
        raise RuntimeError(f"{source_id}: idempotency not yet proven")
    return {
        "raw_drive_evidence": True,
        "latest_sha": str(raw["latest_sha"]),
        "idempotency_proven": idempotent,
        "collector_runs": int(raw["runs"]),
        "load_runs": int(audit_row["runs"]),
    }


def validate_ppm(
    *,
    project_id: str,
    dataset_id: str,
    ops_dataset_id: str,
    location: str,
    require_idempotency: bool,
) -> dict[str, Any]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id, location=location)
    table = f"{project_id}.{dataset_id}.ibge_ppm_cattle_mt"
    latest = f"{project_id}.{dataset_id}.v_ibge_ppm_cattle_mt_latest"
    state_view = f"{project_id}.{dataset_id}.v_ibge_ppm_cattle_mt_state_year"

    base = _one(
        client,
        f"""
SELECT
  COUNT(*) rows_total,
  COUNT(DISTINCT CONCAT(snapshot_id, ':', record_id)) snapshot_record_keys,
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
    if int(base["rows_total"] or 0) <= 0:
        raise RuntimeError("PPM table is empty")
    if int(base["rows_total"]) != int(base["snapshot_record_keys"]):
        raise RuntimeError("PPM duplicate snapshot+record_id detected")
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
SELECT year, municipios_observados, rebanho_bovino_cabecas, historical_pit_guard_preserved
FROM `{state_view}`
ORDER BY year DESC
LIMIT 1
""",
    )
    if int(current["municipios_observados"] or 0) < 100 or float(current["rebanho_bovino_cabecas"] or 0) <= 0:
        raise RuntimeError("PPM latest state aggregate is not material")
    if current["historical_pit_guard_preserved"] is not True:
        raise RuntimeError("PPM state view lost PIT guard")

    latest_count = int(_one(client, f"SELECT COUNT(*) n FROM `{latest}`")["n"] or 0)
    if latest_count <= 0 or latest_count > int(base["rows_total"]):
        raise RuntimeError("PPM latest view count invalid")

    evidence = _source_evidence(
        client,
        project_id=project_id,
        ops_dataset_id=ops_dataset_id,
        source_id=PPM_SOURCE_ID,
        require_idempotency=require_idempotency,
    )
    return {
        "status": "PASS",
        "source_id": PPM_SOURCE_ID,
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
        "temporal_guard": True,
        **evidence,
    }


def validate_slaughter(
    *,
    project_id: str,
    dataset_id: str,
    ops_dataset_id: str,
    location: str,
    require_idempotency: bool,
) -> dict[str, Any]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id, location=location)
    table = f"{project_id}.{dataset_id}.ibge_slaughter_cattle_mt"
    latest = f"{project_id}.{dataset_id}.v_ibge_slaughter_cattle_mt_latest"
    quarterly = f"{project_id}.{dataset_id}.v_ibge_slaughter_cattle_mt_quarterly"

    base = _one(
        client,
        f"""
SELECT
  COUNT(*) rows_total,
  COUNT(DISTINCT CONCAT(snapshot_id, ':', record_id)) snapshot_record_keys,
  COUNT(DISTINCT snapshot_id) snapshots,
  MIN(year) year_min,
  MAX(year) year_max,
  COUNT(DISTINCT CONCAT(CAST(year AS STRING), '-Q', CAST(quarter AS STRING))) quarters,
  COUNT(DISTINCT metric_id) metrics,
  COUNTIF(point_in_time_feature_eligible) pit_leaks,
  COUNTIF(data_publicacao IS NOT NULL) invented_publication_rows,
  COUNTIF(quarter NOT BETWEEN 1 AND 4 OR value < 0) bad_values
FROM `{table}`
""",
    )
    if int(base["rows_total"] or 0) <= 0:
        raise RuntimeError("IBGE Abate table is empty")
    if int(base["rows_total"]) != int(base["snapshot_record_keys"]):
        raise RuntimeError("IBGE Abate duplicate snapshot+record_id detected")
    if int(base["year_min"]) > 1997 or int(base["year_max"]) < 2025:
        raise RuntimeError(f"IBGE Abate historical coverage invalid: {base['year_min']}..{base['year_max']}")
    if int(base["metrics"]) != 2:
        raise RuntimeError(f"IBGE Abate metric count drift: {base['metrics']}")
    if int(base["pit_leaks"]) or int(base["invented_publication_rows"]) or int(base["bad_values"]):
        raise RuntimeError("IBGE Abate temporal/value guard failed")

    recent = _one(
        client,
        f"""
SELECT year, quarter, animais_abatidos_cabecas, peso_carcacas_kg,
       peso_medio_carcaca_kg_cabeca, historical_pit_guard_preserved
FROM `{quarterly}`
ORDER BY year DESC, quarter DESC
LIMIT 1
""",
    )
    heads = float(recent["animais_abatidos_cabecas"] or 0)
    weight = float(recent["peso_carcacas_kg"] or 0)
    avg_weight = float(recent["peso_medio_carcaca_kg_cabeca"] or 0)
    if heads <= 0 or weight <= 0 or not 100 <= avg_weight <= 500:
        raise RuntimeError(
            f"IBGE Abate latest quarter implausible: heads={heads} weight={weight} avg={avg_weight}"
        )
    if recent["historical_pit_guard_preserved"] is not True:
        raise RuntimeError("IBGE Abate quarterly view lost PIT guard")

    latest_count = int(_one(client, f"SELECT COUNT(*) n FROM `{latest}`")["n"] or 0)
    if latest_count <= 0 or latest_count > int(base["rows_total"]):
        raise RuntimeError("IBGE Abate latest view count invalid")

    evidence = _source_evidence(
        client,
        project_id=project_id,
        ops_dataset_id=ops_dataset_id,
        source_id=SLAUGHTER_SOURCE_ID,
        require_idempotency=require_idempotency,
    )
    return {
        "status": "PASS",
        "source_id": SLAUGHTER_SOURCE_ID,
        "table": table,
        "latest_view": latest,
        "quarterly_view": quarterly,
        "rows": int(base["rows_total"]),
        "snapshots": int(base["snapshots"]),
        "year_min": int(base["year_min"]),
        "year_max": int(base["year_max"]),
        "quarters": int(base["quarters"]),
        "latest_period": f"{int(recent['year'])}-Q{int(recent['quarter'])}",
        "latest_heads": heads,
        "latest_carcass_weight_kg": weight,
        "latest_avg_carcass_weight_kg_head": avg_weight,
        "temporal_guard": True,
        **evidence,
    }


def validate_sigsif(
    *,
    project_id: str,
    dataset_id: str,
    ops_dataset_id: str,
    location: str,
    require_idempotency: bool,
) -> dict[str, Any]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id, location=location)
    table = f"{project_id}.{dataset_id}.mapa_sigsif_slaughter_snapshot_mt"
    latest = f"{project_id}.{dataset_id}.v_mapa_sigsif_slaughter_snapshot_mt_latest"
    summary = f"{project_id}.{dataset_id}.v_mapa_sigsif_slaughter_snapshot_mt_summary"

    base = _one(
        client,
        f"""
SELECT
  COUNT(*) rows_total,
  COUNT(DISTINCT CONCAT(snapshot_id, ':', record_id)) snapshot_record_keys,
  COUNT(DISTINCT snapshot_id) snapshots,
  COUNT(DISTINCT sex) sexes,
  COUNT(DISTINCT metric_id) metrics,
  COUNTIF(point_in_time_feature_eligible) pit_leaks,
  COUNTIF(target_role != 'current_sif_crosscheck_not_historical_flow') bad_roles,
  COUNTIF(availability_basis != 'observed_at_collection_time_only') bad_availability,
  COUNTIF(value < 0) bad_values
FROM `{table}`
""",
    )
    if int(base["rows_total"] or 0) <= 0:
        raise RuntimeError("SIGSIF table is empty")
    if int(base["rows_total"]) != int(base["snapshot_record_keys"]):
        raise RuntimeError("SIGSIF duplicate snapshot+record_id detected")
    if int(base["sexes"]) != 2 or int(base["metrics"]) != 2:
        raise RuntimeError("SIGSIF sex/metric contract drift")
    if int(base["pit_leaks"]) or int(base["bad_roles"]) or int(base["bad_availability"]) or int(base["bad_values"]):
        raise RuntimeError("SIGSIF temporal/value guard failed")

    latest_count = int(_one(client, f"SELECT COUNT(*) n FROM `{latest}`")["n"] or 0)
    if latest_count != 2:
        raise RuntimeError(f"SIGSIF latest snapshot must expose exactly two sex rows: {latest_count}")
    current = _one(
        client,
        f"""
SELECT snapshot_date, data_coleta, machos, femeas, total_bovinos,
       participacao_femeas, temporal_semantics
FROM `{summary}`
""",
    )
    total = int(current["total_bovinos"] or 0)
    female_share = float(current["participacao_femeas"] or 0)
    if total <= 0 or not 0 <= female_share <= 1:
        raise RuntimeError(f"SIGSIF latest summary invalid: total={total} female_share={female_share}")
    if current["temporal_semantics"] != "snapshot_collection_date_not_event_period":
        raise RuntimeError("SIGSIF temporal semantics drift")

    evidence = _source_evidence(
        client,
        project_id=project_id,
        ops_dataset_id=ops_dataset_id,
        source_id=SIGSIF_SOURCE_ID,
        require_idempotency=require_idempotency,
    )
    return {
        "status": "PASS",
        "source_id": SIGSIF_SOURCE_ID,
        "table": table,
        "latest_view": latest,
        "summary_view": summary,
        "rows": int(base["rows_total"]),
        "snapshots": int(base["snapshots"]),
        "snapshot_date": str(current["snapshot_date"]),
        "total_bovinos_snapshot": total,
        "female_share": female_share,
        "temporal_guard": True,
        **evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production livestock domain in BigQuery")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="pecuaria")
    parser.add_argument("--ops-dataset", default="agrolog_ops")
    parser.add_argument("--location", default="southamerica-east1")
    parser.add_argument("--scope", choices=("all", "ppm", "slaughter", "sigsif"), default="all")
    parser.add_argument("--require-idempotency", action="store_true")
    args = parser.parse_args()

    validators = {
        "ppm": validate_ppm,
        "slaughter": validate_slaughter,
        "sigsif": validate_sigsif,
    }
    selected = validators if args.scope == "all" else {args.scope: validators[args.scope]}
    try:
        checks = {
            name: validator(
                project_id=args.project,
                dataset_id=args.dataset,
                ops_dataset_id=args.ops_dataset,
                location=args.location,
                require_idempotency=args.require_idempotency,
            )
            for name, validator in selected.items()
        }
        print(json.dumps({"status": "PASS", "checks": checks}, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {"status": "FAIL", "scope": args.scope, "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
