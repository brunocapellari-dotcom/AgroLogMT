from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .nasa_power import PowerObservation

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def power_record_id(row: PowerObservation) -> str:
    payload = json.dumps(
        {
            "date": row.date,
            "latitude": round(row.latitude, 6),
            "longitude": round(row.longitude, 6),
            "parameter": row.parameter,
            "value": row.value,
            "unit": row.unit,
            "evidence_subtype": row.evidence_subtype,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def power_rows(
    rows: list[PowerObservation],
    *,
    snapshot_id: str,
    data_coleta: str,
    source_url: str,
    source_hash: str,
    raw_artifact_ref: str | None,
) -> list[dict[str, Any]]:
    return [
        {
            "snapshot_id": snapshot_id,
            "record_id": power_record_id(row),
            "data_referencia": row.date,
            "latitude": row.latitude,
            "longitude": row.longitude,
            "parameter": row.parameter,
            "value": row.value,
            "unit": row.unit,
            "evidence_class": row.evidence_class,
            "evidence_subtype": row.evidence_subtype,
            "data_coleta": data_coleta,
            "source_url": source_url,
            "source_hash": source_hash,
            "raw_artifact_ref": raw_artifact_ref,
        }
        for row in rows
    ]


class NasaPowerBigQueryLoader:
    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "clima",
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = _safe_identifier(project_id, "project_id")
        self.dataset_id = _safe_identifier(dataset_id, "dataset_id")
        self.location = location
        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)
        self.target_table = f"{self.project_id}.{self.dataset_id}.nasa_power_daily"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_nasa_power_daily_latest"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("data_referencia", "DATE", mode="REQUIRED"),
            field("latitude", "FLOAT", mode="REQUIRED"),
            field("longitude", "FLOAT", mode="REQUIRED"),
            field("parameter", "STRING", mode="REQUIRED"),
            field("value", "FLOAT"),
            field("unit", "STRING"),
            field("evidence_class", "STRING", mode="REQUIRED"),
            field("evidence_subtype", "STRING", mode="REQUIRED"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("source_url", "STRING"),
            field("source_hash", "STRING", mode="REQUIRED"),
            field("raw_artifact_ref", "STRING"),
        ]

    def ensure_objects(self) -> None:
        location = self.location.replace("'", "")
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  data_referencia DATE NOT NULL,
  latitude FLOAT64 NOT NULL,
  longitude FLOAT64 NOT NULL,
  parameter STRING NOT NULL,
  value FLOAT64,
  unit STRING,
  evidence_class STRING NOT NULL,
  evidence_subtype STRING NOT NULL,
  data_coleta TIMESTAMP NOT NULL,
  source_url STRING,
  source_hash STRING NOT NULL,
  raw_artifact_ref STRING
)
PARTITION BY data_referencia
CLUSTER BY parameter, latitude, longitude, snapshot_id
""").result()
        self.client.query(f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY data_referencia, latitude, longitude, parameter
    ORDER BY data_coleta DESC, snapshot_id DESC
  ) AS _rn
  FROM `{self.target_table}`
)
SELECT * EXCEPT(_rn) FROM ranked WHERE _rn=1
""").result()

    def _snapshot_count(self, snapshot_id: str) -> int:
        cfg = self._bigquery.QueryJobConfig(query_parameters=[
            self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)
        ])
        rows = list(self.client.query(
            f"SELECT COUNT(*) n FROM `{self.target_table}` WHERE snapshot_id=@snapshot_id", job_config=cfg
        ).result())
        return int(rows[0]["n"]) if rows else 0

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str) -> dict[str, Any]:
        self.ensure_objects()
        existing = self._snapshot_count(snapshot_id)
        if existing:
            return {"status": "already_loaded", "snapshot_id": snapshot_id, "records_inserted": 0, "records_existing": existing}
        started = datetime.now(timezone.utc)
        stage_ref = f"{self.project_id}.{self.dataset_id}._stg_nasa_power_{snapshot_id[:12]}_{int(started.timestamp())}"
        table = self._bigquery.Table(stage_ref, schema=self._schema())
        table.expires = started + timedelta(hours=2)
        self.client.create_table(table)
        try:
            cfg = self._bigquery.LoadJobConfig(schema=self._schema(), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage_ref, job_config=cfg).result()
            self.client.query(f"""
MERGE `{self.target_table}` T
USING `{stage_ref}` S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)
        inserted = self._snapshot_count(snapshot_id)
        return {"status": "loaded", "snapshot_id": snapshot_id, "records_inserted": inserted, "records_existing": 0}
