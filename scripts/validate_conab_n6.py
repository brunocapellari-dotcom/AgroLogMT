#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.cloud import bigquery

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def safe(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def scalar(client: bigquery.Client, sql: str) -> Any:
    rows = list(client.query(sql).result())
    if not rows:
        return None
    return rows[0][0]


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate de homologação N6 para CONAB Armazéns no BigQuery real")
    ap.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    ap.add_argument("--dataset", default=os.environ.get("AGROLOG_LOGISTICA_DATASET", "logistica"))
    ap.add_argument("--ops-dataset", default=os.environ.get("AGROLOG_OPS_DATASET", "agrolog_ops"))
    ap.add_argument("--location", default=os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1"))
    ap.add_argument("--out")
    args = ap.parse_args()
    if not args.project:
        raise SystemExit("Defina --project, AGROLOG_GCP_PROJECT ou GOOGLE_CLOUD_PROJECT")

    project = safe(args.project, "project")
    dataset = safe(args.dataset, "dataset")
    ops = safe(args.ops_dataset, "ops_dataset")
    client = bigquery.Client(project=project, location=args.location)
    table = f"{project}.{dataset}.armazens_conab"
    latest = f"{project}.{dataset}.v_armazens_conab_latest"
    audit = f"{project}.{ops}.domain_load_runs"
    collector_runs = f"{project}.{ops}.collector_runs"

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, value: Any, rule: str, severity: str = "blocking") -> None:
        checks.append({"name": name, "passed": bool(passed), "value": value, "rule": rule, "severity": severity})

    metadata = client.get_table(table)
    schema_names = {field.name for field in metadata.schema}
    required_schema = {
        "snapshot_id", "record_id", "warehouse_id", "source_id", "municipio", "uf",
        "capacidade_estatica_t", "data_referencia", "data_coleta", "competencia",
        "evidence_class", "source_hash", "quality_score", "quality_flags",
    }
    missing_schema = sorted(required_schema - schema_names)
    add("required_schema_present", not missing_schema, missing_schema, "no missing required fields")
    partition_field = metadata.time_partitioning.field if metadata.time_partitioning else None
    add("partition_by_reference_date", partition_field == "data_referencia", partition_field, "data_referencia")
    clustering = list(metadata.clustering_fields or [])
    add(
        "expected_clustering",
        clustering == ["uf", "municipio", "warehouse_id", "snapshot_id"],
        clustering,
        "uf,municipio,warehouse_id,snapshot_id",
    )

    latest_rows = int(scalar(client, f"SELECT COUNT(*) FROM `{latest}`") or 0)
    add("latest_non_empty", latest_rows > 0, latest_rows, "> 0")

    duplicate_rows = int(scalar(client, f"""
        SELECT COUNT(*) FROM (
          SELECT snapshot_id, record_id, COUNT(*) n
          FROM `{table}` GROUP BY snapshot_id, record_id HAVING n > 1
        )
    """) or 0)
    add("no_duplicate_record_in_snapshot", duplicate_rows == 0, duplicate_rows, "= 0")

    invalid_dates = int(scalar(client, f"""
        SELECT COUNT(*) FROM `{latest}`
        WHERE data_referencia IS NULL OR data_coleta IS NULL OR competencia IS NULL OR TRIM(competencia)=''
    """) or 0)
    add("canonical_dates_present", invalid_dates == 0, invalid_dates, "= 0")

    invalid_geo = int(scalar(client, f"""
        SELECT COUNT(*) FROM `{latest}`
        WHERE uf IS NULL OR LENGTH(uf) != 2 OR municipio IS NULL OR TRIM(municipio)=''
           OR (latitude IS NOT NULL AND NOT BETWEEN(latitude,-90,90))
           OR (longitude IS NOT NULL AND NOT BETWEEN(longitude,-180,180))
    """) or 0)
    add("geography_structurally_valid", invalid_geo == 0, invalid_geo, "= 0")

    negative_capacity = int(scalar(client, f"SELECT COUNT(*) FROM `{latest}` WHERE capacidade_estatica_t < 0") or 0)
    add("no_negative_capacity", negative_capacity == 0, negative_capacity, "= 0")

    observed_mismatch = int(scalar(client, f"SELECT COUNT(*) FROM `{latest}` WHERE evidence_class != 'observado'") or 0)
    add("evidence_class_observed", observed_mismatch == 0, observed_mismatch, "= 0")

    latest_snapshot = scalar(client, f"SELECT snapshot_id FROM `{latest}` LIMIT 1")
    add("latest_snapshot_identified", bool(latest_snapshot), latest_snapshot, "not null")

    audit_runs = int(scalar(client, f"SELECT COUNT(*) FROM `{audit}` WHERE source_id='conab_armazens_cadastrados'") or 0)
    add("domain_audit_exists", audit_runs > 0, audit_runs, "> 0")

    collector_evidence_rows = list(client.query(f"""
        SELECT status, sha256, raw_artifact_ref, data_coleta
        FROM `{collector_runs}`
        WHERE source_id='conab_armazens_cadastrados'
        ORDER BY inserted_at DESC LIMIT 10
    """).result())
    collector_evidence = [dict(row.items()) for row in collector_evidence_rows]
    has_raw = any(
        row.get("sha256") and str(row.get("raw_artifact_ref") or "").startswith(("gs://", "drive://"))
        for row in collector_evidence
    )
    add("raw_manifest_with_hash_exists", has_raw, collector_evidence[:3], "sha256 + durable RAW artifact ref (gs:// or drive://)")

    if latest_snapshot:
        run_statuses = [row[0] for row in client.query(f"""
            SELECT status FROM `{audit}`
            WHERE source_id='conab_armazens_cadastrados' AND snapshot_id=@snapshot
            ORDER BY finished_at DESC LIMIT 10
        """, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("snapshot", "STRING", latest_snapshot)
        ])).result()]
    else:
        run_statuses = []
    add("snapshot_has_successful_load", any(s in {"loaded", "already_loaded"} for s in run_statuses), run_statuses, "loaded/already_loaded present")
    add("idempotency_proven", "already_loaded" in run_statuses, run_statuses, "already_loaded present after second execution")

    mt_rows = list(client.query(f"""
        SELECT COUNT(DISTINCT warehouse_id) AS unidades,
               SUM(COALESCE(capacidade_estatica_t,0)) AS capacidade_estatica_t,
               AVG(quality_score) AS quality_score_medio,
               COUNTIF(cda IS NULL OR TRIM(cda)='') AS sem_cda,
               COUNTIF(cnpj IS NULL OR TRIM(cnpj)='') AS sem_cnpj,
               COUNTIF(latitude IS NULL OR longitude IS NULL) AS sem_coordenadas,
               COUNTIF(quality_score < 0.5) AS baixa_qualidade
        FROM `{latest}` WHERE uf='MT'
    """).result())
    mt = dict(mt_rows[0].items()) if mt_rows else {}
    add("mt_has_data", int(mt.get("unidades") or 0) > 0, mt, "unidades > 0")
    add(
        "mt_quality_profile_recorded",
        True,
        mt,
        "profile only; missing CDA/CNPJ/coordinates are source-quality signals, not automatic rejection",
        severity="warning",
    )

    blocking_failed = [c for c in checks if c["severity"] == "blocking" and not c["passed"]]
    warnings = [c for c in checks if c["severity"] == "warning" and not c["passed"]]
    report = {
        "status": "PASS" if not blocking_failed else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "dataset": dataset,
        "latest_snapshot": latest_snapshot,
        "checks": checks,
        "blocking_failures": len(blocking_failed),
        "warnings": len(warnings),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if not blocking_failed else 1


if __name__ == "__main__":
    sys.exit(main())
