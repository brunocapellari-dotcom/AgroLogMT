from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .snapshot_bigquery import (
    ensure_dataset,
    ensure_domain_audit_table,
    merge_snapshot_rows,
    safe_identifier,
    snapshot_count,
    write_domain_audit,
)

_safe_identifier = safe_identifier


@dataclass(frozen=True)
class PamLoadResult:
    status: str
    snapshot_id: str
    records_input: int
    records_inserted: int
    records_existing: int
    target_table: str
    audit_table: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IbgePamBigQueryLoader:
    """Idempotent loader for realized PAM soybean yield labels in Mato Grosso."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "agro",
        ops_dataset_id: str = "agrolog_ops",
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = safe_identifier(project_id, "project_id")
        self.dataset_id = safe_identifier(dataset_id, "dataset_id")
        self.ops_dataset_id = safe_identifier(ops_dataset_id, "ops_dataset_id")
        self.location = location
        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)
        self.target_table = f"{self.project_id}.{self.dataset_id}.ibge_pam_soy_mt_yield"
        self.audit_table = f"{self.project_id}.{self.ops_dataset_id}.domain_load_runs"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("source_id", "STRING", mode="REQUIRED"),
            field("geo_level", "STRING", mode="REQUIRED"),
            field("geo_id", "STRING", mode="REQUIRED"),
            field("geo_code_ibge", "STRING", mode="REQUIRED"),
            field("product_id", "STRING", mode="REQUIRED"),
            field("metric_id", "STRING", mode="REQUIRED"),
            field("year", "INT64", mode="REQUIRED"),
            field("value", "FLOAT", mode="REQUIRED"),
            field("unit", "STRING", mode="REQUIRED"),
            field("data_referencia", "DATE", mode="REQUIRED"),
            field("data_publicacao", "TIMESTAMP"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("data_disponibilidade", "TIMESTAMP"),
            field("availability_verified", "BOOL", mode="REQUIRED"),
            field("availability_basis", "STRING", mode="REQUIRED"),
            field("point_in_time_feature_eligible", "BOOL", mode="REQUIRED"),
            field("target_role", "STRING", mode="REQUIRED"),
            field("competencia", "STRING", mode="REQUIRED"),
            field("evidence_class", "STRING", mode="REQUIRED"),
            field("methodology_id", "STRING", mode="REQUIRED"),
            field("raw_artifact_ref", "STRING"),
            field("source_url", "STRING", mode="REQUIRED"),
            field("source_hash", "STRING", mode="REQUIRED"),
            field("collector_version", "STRING"),
            field("quality_score", "FLOAT"),
            field("quality_flags", "STRING", mode="REPEATED"),
        ]

    def ensure_objects(self) -> None:
        ensure_dataset(
            self.client,
            project_id=self.project_id,
            dataset_id=self.dataset_id,
            location=self.location,
        )
        self.audit_table = ensure_domain_audit_table(
            self.client,
            project_id=self.project_id,
            ops_dataset_id=self.ops_dataset_id,
            location=self.location,
        )
        self.client.query(
            f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  source_id STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_id STRING NOT NULL,
  geo_code_ibge STRING NOT NULL,
  product_id STRING NOT NULL,
  metric_id STRING NOT NULL,
  year INT64 NOT NULL,
  value FLOAT64 NOT NULL,
  unit STRING NOT NULL,
  data_referencia DATE NOT NULL,
  data_publicacao TIMESTAMP,
  data_coleta TIMESTAMP NOT NULL,
  data_disponibilidade TIMESTAMP,
  availability_verified BOOL NOT NULL,
  availability_basis STRING NOT NULL,
  point_in_time_feature_eligible BOOL NOT NULL,
  target_role STRING NOT NULL,
  competencia STRING NOT NULL,
  evidence_class STRING NOT NULL,
  methodology_id STRING NOT NULL,
  raw_artifact_ref STRING,
  source_url STRING NOT NULL,
  source_hash STRING NOT NULL,
  collector_version STRING,
  quality_score FLOAT64,
  quality_flags ARRAY<STRING>
)
PARTITION BY data_referencia
CLUSTER BY geo_id, product_id, year, snapshot_id
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.project_id}.{self.dataset_id}.v_ibge_pam_soy_mt_yield_latest` AS
SELECT * EXCEPT(rn)
FROM (
  SELECT *, ROW_NUMBER() OVER(PARTITION BY year ORDER BY data_coleta DESC, snapshot_id DESC) rn
  FROM `{self.target_table}`
)
WHERE rn=1
"""
        ).result()

    def _snapshot_count(self, snapshot_id: str) -> int:
        return snapshot_count(
            self.client,
            self._bigquery,
            target_table=self.target_table,
            snapshot_id=snapshot_id,
        )

    def _write_audit(self, row: dict[str, Any]) -> None:
        write_domain_audit(
            self.client,
            audit_table=self.audit_table,
            row=row,
            error_label="IBGE PAM",
        )

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str, parse_stats: dict[str, Any]) -> PamLoadResult:
        if not rows:
            raise ValueError("IBGE PAM rows empty")
        started = datetime.now(timezone.utc)
        self.ensure_objects()
        status, persisted, existing = merge_snapshot_rows(
            self.client,
            self._bigquery,
            target_table=self.target_table,
            schema=self._schema(),
            rows=rows,
            snapshot_id=snapshot_id,
            stage_prefix="ibge_pam",
            started_at=started,
        )
        finished = datetime.now(timezone.utc)
        result = PamLoadResult(
            status,
            snapshot_id,
            len(rows),
            0 if status == "already_loaded" else persisted,
            existing,
            self.target_table,
            self.audit_table,
            started.isoformat(),
            finished.isoformat(),
        )
        self._write_audit({
            "run_id": f"ibge_pam:{snapshot_id}:{started.isoformat()}",
            "source_id": "ibge_sidra_pam_1612",
            "domain": "agro.realized_target",
            "target_table": self.target_table,
            "snapshot_id": snapshot_id,
            "status": status,
            "records_read": parse_stats.get("records_read"),
            "records_accepted": parse_stats.get("records_accepted"),
            "records_rejected": parse_stats.get("records_rejected", 0),
            "duplicates_removed": 0,
            "records_inserted": 0 if status == "already_loaded" else persisted,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
        })
        return result
