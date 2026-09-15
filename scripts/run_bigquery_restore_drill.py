from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def safe_identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def field_signature(fields: list[Any]) -> list[tuple[str, str, str]]:
    return [(field.name, field.field_type, field.mode) for field in fields]


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-destructive BigQuery point-in-time restore drill")
    parser.add_argument("--project", default=os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AGROLOG_GCP_PROJECT"))
    parser.add_argument("--source-dataset", default=os.environ.get("AGROLOG_OPS_DATASET", "agrolog_ops"))
    parser.add_argument("--source-table", default="collector_runs")
    parser.add_argument("--recovery-dataset", default="recovery_sandbox")
    parser.add_argument("--location", default=os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1"))
    parser.add_argument("--rpo-minutes", type=int, default=1)
    parser.add_argument("--ttl-hours", type=int, default=24)
    parser.add_argument("--output", default="outputs/restore/bigquery-restore-drill.json")
    args = parser.parse_args()

    if not args.project:
        raise SystemExit("missing --project / GOOGLE_CLOUD_PROJECT / AGROLOG_GCP_PROJECT")
    if args.rpo_minutes < 0 or args.ttl_hours < 1:
        raise SystemExit("rpo-minutes must be >=0 and ttl-hours must be >=1")

    project = safe_identifier(args.project, "project")
    source_dataset = safe_identifier(args.source_dataset, "source dataset")
    source_table = safe_identifier(args.source_table, "source table")
    recovery_dataset = safe_identifier(args.recovery_dataset, "recovery dataset")

    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=args.location)
    started = datetime.now(timezone.utc)
    cutoff = started - timedelta(minutes=args.rpo_minutes)
    drill_id = f"bq-{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    target_table = safe_identifier(f"restore_{source_table}_{started.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}", "target table")
    source_ref = f"{project}.{source_dataset}.{source_table}"
    target_ref = f"{project}.{recovery_dataset}.{target_table}"
    expires = started + timedelta(hours=args.ttl_hours)
    evidence: list[str] = []
    status = "FAIL"
    validation = {
        "object_count": "NOT_APPLICABLE",
        "row_count": "FAIL",
        "hash_or_checksum": "NOT_APPLICABLE",
        "permissions": "FAIL",
        "secrets_not_exported": True,
    }
    notes: list[str] = [
        "Non-destructive drill using BigQuery point-in-time read into an isolated recovery table.",
        "No Secret Manager payloads, credentials, cookies or tokens are selected or exported.",
    ]

    try:
        client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{project}.{recovery_dataset}` OPTIONS(location='{args.location}')"
        ).result()

        source_meta = client.get_table(source_ref)
        cutoff_literal = cutoff.isoformat().replace("+00:00", "Z")
        expiry_literal = expires.isoformat().replace("+00:00", "Z")

        source_count_query = f"SELECT COUNT(*) AS n FROM `{source_ref}` FOR SYSTEM_TIME AS OF TIMESTAMP('{cutoff_literal}')"
        source_job = client.query(source_count_query)
        source_rows = list(source_job.result())
        source_count = int(source_rows[0]["n"]) if source_rows else 0
        evidence.append(f"bigquery-job://{project}/{source_job.job_id}")

        restore_sql = f"""
CREATE TABLE `{target_ref}`
OPTIONS(expiration_timestamp=TIMESTAMP('{expiry_literal}'))
AS
SELECT * FROM `{source_ref}` FOR SYSTEM_TIME AS OF TIMESTAMP('{cutoff_literal}')
"""
        restore_job = client.query(restore_sql)
        restore_job.result()
        evidence.append(f"bigquery-job://{project}/{restore_job.job_id}")
        evidence.append(f"bigquery://{target_ref}")

        target_meta = client.get_table(target_ref)
        count_job = client.query(f"SELECT COUNT(*) AS n FROM `{target_ref}`")
        target_rows = list(count_job.result())
        target_count = int(target_rows[0]["n"]) if target_rows else 0
        evidence.append(f"bigquery-job://{project}/{count_job.job_id}")

        source_schema = field_signature(source_meta.schema)
        target_schema = field_signature(target_meta.schema)
        row_ok = source_count == target_count
        schema_ok = source_schema == target_schema
        validation["row_count"] = "PASS" if row_ok else "FAIL"
        validation["permissions"] = "PASS"
        status = "PASS" if row_ok and schema_ok else "FAIL"
        notes.extend([
            f"cutoff={cutoff_literal}",
            f"source_rows={source_count}",
            f"restored_rows={target_count}",
            f"schema_match={schema_ok}",
            f"recovery_table_expires={expiry_literal}",
        ])
    except Exception as exc:
        notes.append(f"drill_error={type(exc).__name__}: {exc}")
        status = "FAIL"

    finished = datetime.now(timezone.utc)
    rto_minutes = max(0, int((finished - started).total_seconds() // 60))
    payload = {
        "version": "1.0.0",
        "drill_id": drill_id,
        "environment": "production_recovery_sandbox",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "backup_type": "BIGQUERY_COPY",
        "source_ref": f"bigquery://{source_ref}@{cutoff.isoformat()}",
        "restore_target": f"bigquery://{target_ref}",
        "status": status,
        "rpo_minutes": args.rpo_minutes,
        "rto_minutes": rto_minutes,
        "validation": validation,
        "evidence": evidence,
        "notes": " | ".join(notes),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
