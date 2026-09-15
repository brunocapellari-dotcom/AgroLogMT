from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} invalido: {value!r}")
    return value


@dataclass(frozen=True)
class PpmLoadResult:
    status: str
    snapshot_id: str
    records_input: int
    records_persisted: int
    records_existing: int
    target_table: str
    latest_view: str
    state_view: str
    audit_table: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IbgePpmBigQueryLoader:
    """Idempotent loader for IBGE PPM municipal cattle herd history in Mato Grosso."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "pecuaria",
        ops_dataset_id: str = "agrolog_ops",
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = _safe_identifier(project_id, "project_id")
        self.dataset_id = _safe_identifier(dataset_id, "dataset_id")
        self.ops_dataset_id = _safe_identifier(ops_dataset_id, "ops_dataset_id")
        self.location = location
        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)
        self.target_table = f"{self.project_id}.{self.dataset_id}.ibge_ppm_cattle_mt"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_ibge_ppm_cattle_mt_latest"
        self.state_view = f"{self.project_id}.{self.dataset_id}.v_ibge_ppm_cattle_mt_state_year"
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
            field("geo_name", "STRING", mode="REQUIRED"),
            field("product_id", "STRING", mode="REQUIRED"),
            field("metric_id", "STRING", mode="REQUIRED"),
            field("year", "INT64", mode="REQUIRED"),
            field("value", "FLOAT64", mode="REQUIRED"),
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
            field("quality_score", "FLOAT64"),
            field("quality_flags", "STRING", mode="REPEATED"),
        ]

    def ensure_objects(self) -> None:
        location = self.location.replace("'", "")
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.ops_dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(
            f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  source_id STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_id STRING NOT NULL,
  geo_code_ibge STRING NOT NULL,
  geo_name STRING NOT NULL,
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
CLUSTER BY geo_code_ibge, year, snapshot_id
"""
        ).result()
        self.client.query(
            f"""
CREATE TABLE IF NOT EXISTS `{self.audit_table}` (
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
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
SELECT * EXCEPT(rn)
FROM (
  SELECT *, ROW_NUMBER() OVER(
    PARTITION BY geo_code_ibge, year
    ORDER BY data_coleta DESC, snapshot_id DESC
  ) rn
  FROM `{self.target_table}`
)
WHERE rn=1
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.state_view}` AS
SELECT
  year,
  DATE(CONCAT(CAST(year AS STRING), '-12-31')) AS data_referencia,
  COUNT(DISTINCT geo_code_ibge) AS municipios_observados,
  SUM(value) AS rebanho_bovino_cabecas,
  ANY_VALUE(unit) AS unit,
  MAX(data_coleta) AS ultima_coleta,
  LOGICAL_AND(NOT point_in_time_feature_eligible) AS historical_pit_guard_preserved
FROM `{self.latest_view}`
GROUP BY year
"""
        ).result()

    def _snapshot_count(self, snapshot_id: str) -> int:
        cfg = self._bigquery.QueryJobConfig(
            query_parameters=[self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)]
        )
        rows = list(
            self.client.query(
                f"SELECT COUNT(*) AS n FROM `{self.target_table}` WHERE snapshot_id=@snapshot_id",
                job_config=cfg,
            ).result()
        )
        return int(rows[0]["n"]) if rows else 0

    def _write_audit(self, row: dict[str, Any]) -> None:
        errors = self.client.insert_rows_json(self.audit_table, [row])
        if errors:
            raise RuntimeError(f"Falha ao gravar auditoria IBGE PPM: {errors}")

    @staticmethod
    def _validate_rows(rows: list[dict[str, Any]], snapshot_id: str) -> None:
        if not rows:
            raise ValueError("IBGE PPM rows empty")
        seen: set[str] = set()
        for row in rows:
            if row.get("snapshot_id") != snapshot_id:
                raise ValueError("IBGE PPM snapshot_id inconsistente")
            if row.get("point_in_time_feature_eligible") is not False:
                raise ValueError("IBGE PPM histórico não pode ser promovido como feature point-in-time")
            record_id = str(row.get("record_id") or "")
            if not record_id or record_id in seen:
                raise ValueError("IBGE PPM record_id ausente ou duplicado")
            seen.add(record_id)

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str, parse_stats: dict[str, Any]) -> PpmLoadResult:
        self._validate_rows(rows, snapshot_id)
        started = datetime.now(timezone.utc)
        self.ensure_objects()
        existing = self._snapshot_count(snapshot_id)
        run_id = f"ibge_ppm:{snapshot_id}:{started.isoformat()}"
        if existing:
            if existing != len(rows):
                raise RuntimeError(
                    f"IBGE PPM snapshot parcial/inconsistente: esperado={len(rows)} persistido={existing}"
                )
            finished = datetime.now(timezone.utc)
            result = PpmLoadResult(
                "already_loaded", snapshot_id, len(rows), existing, existing,
                self.target_table, self.latest_view, self.state_view, self.audit_table,
                started.isoformat(), finished.isoformat(),
            )
            self._write_audit({
                "run_id": run_id,
                "source_id": "ibge_sidra_ppm_3939",
                "domain": "pecuaria.herd_stock",
                "target_table": self.target_table,
                "snapshot_id": snapshot_id,
                "status": result.status,
                "records_read": parse_stats.get("records_read"),
                "records_accepted": parse_stats.get("records_accepted"),
                "records_rejected": parse_stats.get("records_rejected", 0),
                "duplicates_removed": 0,
                "records_inserted": 0,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
            })
            return result

        stage_ref = (
            f"{self.project_id}.{self.dataset_id}._stg_ibge_ppm_"
            f"{snapshot_id[:12]}_{int(started.timestamp())}"
        )
        table = self._bigquery.Table(stage_ref, schema=self._schema())
        table.expires = started + timedelta(hours=2)
        self.client.create_table(table)
        try:
            cfg = self._bigquery.LoadJobConfig(schema=self._schema(), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage_ref, job_config=cfg).result()
            self.client.query(
                f"""
MERGE `{self.target_table}` T
USING `{stage_ref}` S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
"""
            ).result()
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)

        persisted = self._snapshot_count(snapshot_id)
        if persisted != len(rows):
            raise RuntimeError(
                f"Tie-out IBGE PPM falhou: esperado={len(rows)} persistido={persisted}"
            )
        finished = datetime.now(timezone.utc)
        result = PpmLoadResult(
            "loaded", snapshot_id, len(rows), persisted, 0,
            self.target_table, self.latest_view, self.state_view, self.audit_table,
            started.isoformat(), finished.isoformat(),
        )
        self._write_audit({
            "run_id": run_id,
            "source_id": "ibge_sidra_ppm_3939",
            "domain": "pecuaria.herd_stock",
            "target_table": self.target_table,
            "snapshot_id": snapshot_id,
            "status": result.status,
            "records_read": parse_stats.get("records_read"),
            "records_accepted": parse_stats.get("records_accepted"),
            "records_rejected": parse_stats.get("records_rejected", 0),
            "duplicates_removed": 0,
            "records_inserted": persisted,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
        })
        return result
