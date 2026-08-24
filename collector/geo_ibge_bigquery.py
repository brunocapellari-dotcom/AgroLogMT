from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .geo_ibge import Municipality

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def municipality_record_id(row: Municipality) -> str:
    payload = json.dumps(
        {
            "codigo_ibge": row.codigo_ibge,
            "municipio": row.municipio,
            "uf": row.uf,
            "uf_codigo_ibge": row.uf_codigo_ibge,
            "mesorregiao": row.mesorregiao,
            "microrregiao": row.microrregiao,
            "regiao_imediata": row.regiao_imediata,
            "regiao_intermediaria": row.regiao_intermediaria,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def municipality_rows(
    rows: list[Municipality],
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
            "record_id": municipality_record_id(row),
            "codigo_ibge": row.codigo_ibge,
            "municipio": row.municipio,
            "uf": row.uf,
            "uf_codigo_ibge": row.uf_codigo_ibge,
            "mesorregiao": row.mesorregiao,
            "microrregiao": row.microrregiao,
            "regiao_imediata": row.regiao_imediata,
            "regiao_intermediaria": row.regiao_intermediaria,
            "source_id": row.source_id,
            "evidence_class": row.evidence_class,
            "data_coleta": data_coleta,
            "source_url": source_url,
            "source_hash": source_hash,
            "raw_artifact_ref": raw_artifact_ref,
        }
        for row in rows
    ]


class IbgeMunicipalityBigQueryLoader:
    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "referencia",
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = _safe_identifier(project_id, "project_id")
        self.dataset_id = _safe_identifier(dataset_id, "dataset_id")
        self.location = location
        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)
        self.target_table = f"{self.project_id}.{self.dataset_id}.municipios_ibge"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_municipios_ibge_latest"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("codigo_ibge", "INT64", mode="REQUIRED"),
            field("municipio", "STRING", mode="REQUIRED"),
            field("uf", "STRING", mode="REQUIRED"),
            field("uf_codigo_ibge", "INT64"),
            field("mesorregiao", "STRING"),
            field("microrregiao", "STRING"),
            field("regiao_imediata", "STRING"),
            field("regiao_intermediaria", "STRING"),
            field("source_id", "STRING", mode="REQUIRED"),
            field("evidence_class", "STRING", mode="REQUIRED"),
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
  codigo_ibge INT64 NOT NULL,
  municipio STRING NOT NULL,
  uf STRING NOT NULL,
  uf_codigo_ibge INT64,
  mesorregiao STRING,
  microrregiao STRING,
  regiao_imediata STRING,
  regiao_intermediaria STRING,
  source_id STRING NOT NULL,
  evidence_class STRING NOT NULL,
  data_coleta TIMESTAMP NOT NULL,
  source_url STRING,
  source_hash STRING NOT NULL,
  raw_artifact_ref STRING
)
CLUSTER BY uf, codigo_ibge, snapshot_id
""").result()
        self.client.query(f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
WITH latest AS (
  SELECT snapshot_id
  FROM `{self.target_table}`
  GROUP BY snapshot_id
  ORDER BY MAX(data_coleta) DESC
  LIMIT 1
)
SELECT * FROM `{self.target_table}`
WHERE snapshot_id = (SELECT snapshot_id FROM latest)
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
        stage_ref = f"{self.project_id}.{self.dataset_id}._stg_municipios_ibge_{snapshot_id[:12]}_{int(started.timestamp())}"
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
