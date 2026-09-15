from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} invalido: {value!r}")
    return value


def ensure_dataset(client: Any, *, project_id: str, dataset_id: str, location: str) -> None:
    project = safe_identifier(project_id, "project_id")
    dataset = safe_identifier(dataset_id, "dataset_id")
    safe_location = location.replace("'", "")
    client.query(
        f"CREATE SCHEMA IF NOT EXISTS `{project}.{dataset}` OPTIONS(location='{safe_location}')"
    ).result()


def ensure_domain_audit_table(
    client: Any,
    *,
    project_id: str,
    ops_dataset_id: str,
    location: str,
) -> str:
    project = safe_identifier(project_id, "project_id")
    dataset = safe_identifier(ops_dataset_id, "ops_dataset_id")
    ensure_dataset(client, project_id=project, dataset_id=dataset, location=location)
    audit_table = f"{project}.{dataset}.domain_load_runs"
    client.query(
        f"""
CREATE TABLE IF NOT EXISTS `{audit_table}` (
  run_id STRING NOT NULL,
  source_id STRING NOT NULL,
  domain STRING NOT NULL,
  target_table STRING NOT NULL,
  snapshot_id STRING,
  status STRING NOT NULL,
  records_read INT64,
  records_accepted INT64,
  records_rejected INT64,
  duplicates_removed INT64,
  records_inserted INT64,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP NOT NULL,
  details_json STRING
)
PARTITION BY DATE(finished_at)
CLUSTER BY source_id, domain, status
"""
    ).result()
    return audit_table


def snapshot_count(
    client: Any,
    bigquery_module: Any,
    *,
    target_table: str,
    snapshot_id: str,
) -> int:
    config = bigquery_module.QueryJobConfig(
        query_parameters=[bigquery_module.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)]
    )
    rows = list(
        client.query(
            f"SELECT COUNT(*) AS n FROM `{target_table}` WHERE snapshot_id=@snapshot_id",
            job_config=config,
        ).result()
    )
    return int(rows[0]["n"]) if rows else 0


def merge_snapshot_rows(
    client: Any,
    bigquery_module: Any,
    *,
    target_table: str,
    schema: list[Any],
    rows: list[dict[str, Any]],
    snapshot_id: str,
    stage_prefix: str,
    started_at: datetime,
) -> tuple[str, int, int]:
    """Idempotently persist an immutable source snapshot and enforce exact tie-out.

    Returns ``(status, persisted_count, existing_count)``. A partial pre-existing
    snapshot fails closed instead of attempting to repair it silently.
    """
    if not rows:
        raise ValueError("snapshot rows empty")

    existing = snapshot_count(
        client,
        bigquery_module,
        target_table=target_table,
        snapshot_id=snapshot_id,
    )
    if existing:
        if existing != len(rows):
            raise RuntimeError(
                f"snapshot parcial/inconsistente em {target_table}: "
                f"esperado={len(rows)} persistido={existing}"
            )
        return "already_loaded", existing, existing

    safe_prefix = re.sub(r"[^A-Za-z0-9_]", "_", stage_prefix)[:80] or "snapshot"
    dataset_prefix = target_table.rsplit(".", 1)[0]
    stage_ref = f"{dataset_prefix}._stg_{safe_prefix}_{snapshot_id[:12]}_{int(started_at.timestamp())}"
    stage = bigquery_module.Table(stage_ref, schema=schema)
    stage.expires = started_at + timedelta(hours=2)
    client.create_table(stage)
    try:
        config = bigquery_module.LoadJobConfig(
            schema=schema,
            write_disposition="WRITE_TRUNCATE",
        )
        client.load_table_from_json(rows, stage_ref, job_config=config).result()
        client.query(
            f"""
MERGE `{target_table}` T
USING `{stage_ref}` S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
"""
        ).result()
    finally:
        client.delete_table(stage_ref, not_found_ok=True)

    persisted = snapshot_count(
        client,
        bigquery_module,
        target_table=target_table,
        snapshot_id=snapshot_id,
    )
    if persisted != len(rows):
        raise RuntimeError(
            f"tie-out snapshot falhou em {target_table}: esperado={len(rows)} persistido={persisted}"
        )
    return "loaded", persisted, 0


def write_domain_audit(
    client: Any,
    *,
    audit_table: str,
    row: dict[str, Any],
    error_label: str,
) -> None:
    errors = client.insert_rows_json(audit_table, [row])
    if errors:
        raise RuntimeError(f"Falha ao gravar auditoria {error_label}: {errors}")
