from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .snapshot_bigquery import (
    ensure_domain_audit_table,
    merge_snapshot_rows,
    require_dataset,
    safe_identifier,
    snapshot_count,
    write_domain_audit,
)

HEAD_METRIC = "pecuaria.abate_bovino_cabecas"
WEIGHT_METRIC = "pecuaria.abate_bovino_peso_carcaca"


@dataclass(frozen=True)
class SlaughterLoadResult:
    status: str
    snapshot_id: str
    records_input: int
    records_persisted: int
    records_existing: int
    target_table: str
    latest_view: str
    quarterly_view: str
    audit_table: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IbgeSlaughterBigQueryLoader:
    """Revision-aware loader for IBGE quarterly cattle slaughter in Mato Grosso."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "pecuaria",
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
        self.target_table = f"{self.project_id}.{self.dataset_id}.ibge_slaughter_cattle_mt"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_ibge_slaughter_cattle_mt_latest"
        self.quarterly_view = f"{self.project_id}.{self.dataset_id}.v_ibge_slaughter_cattle_mt_quarterly"
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
            field("quarter", "INT64", mode="REQUIRED"),
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
        require_dataset(
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
  geo_name STRING NOT NULL,
  product_id STRING NOT NULL,
  metric_id STRING NOT NULL,
  year INT64 NOT NULL,
  quarter INT64 NOT NULL,
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
CLUSTER BY year, quarter, metric_id, snapshot_id
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
SELECT * EXCEPT(rn)
FROM (
  SELECT *, ROW_NUMBER() OVER(
    PARTITION BY year, quarter, metric_id
    ORDER BY data_coleta DESC, snapshot_id DESC
  ) rn
  FROM `{self.target_table}`
)
WHERE rn=1
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.quarterly_view}` AS
WITH q AS (
  SELECT
    year,
    quarter,
    MAX(data_referencia) AS data_referencia,
    MAX(IF(metric_id='{HEAD_METRIC}', value, NULL)) AS animais_abatidos_cabecas,
    MAX(IF(metric_id='{WEIGHT_METRIC}', value, NULL)) AS peso_carcacas_kg,
    MAX(data_coleta) AS ultima_coleta,
    LOGICAL_AND(NOT point_in_time_feature_eligible) AS historical_pit_guard_preserved
  FROM `{self.latest_view}`
  GROUP BY year, quarter
)
SELECT
  *,
  SAFE_DIVIDE(peso_carcacas_kg, animais_abatidos_cabecas) AS peso_medio_carcaca_kg_cabeca
FROM q
"""
        ).result()

    @staticmethod
    def _validate_rows(rows: list[dict[str, Any]], snapshot_id: str) -> None:
        if not rows:
            raise ValueError("IBGE Abate rows empty")
        seen: set[str] = set()
        period_metrics: dict[tuple[int, int], set[str]] = {}
        for row in rows:
            if row.get("snapshot_id") != snapshot_id:
                raise ValueError("IBGE Abate snapshot_id inconsistente")
            if row.get("point_in_time_feature_eligible") is not False:
                raise ValueError("IBGE Abate histórico não pode ser promovido como feature point-in-time")
            record_id = str(row.get("record_id") or "")
            if not record_id or record_id in seen:
                raise ValueError("IBGE Abate record_id ausente ou duplicado")
            seen.add(record_id)
            year = int(row.get("year") or 0)
            quarter = int(row.get("quarter") or 0)
            metric_id = str(row.get("metric_id") or "")
            value = float(row.get("value") or 0)
            if year < 1997 or quarter not in {1, 2, 3, 4} or value < 0:
                raise ValueError("IBGE Abate período/valor inválido")
            if metric_id not in {HEAD_METRIC, WEIGHT_METRIC}:
                raise ValueError(f"IBGE Abate métrica fora do contrato: {metric_id}")
            period_metrics.setdefault((year, quarter), set()).add(metric_id)
        incomplete = sorted(period for period, metrics in period_metrics.items() if metrics != {HEAD_METRIC, WEIGHT_METRIC})
        if incomplete:
            raise ValueError(f"IBGE Abate trimestre sem as duas métricas oficiais: {incomplete[:5]}")

    def _snapshot_count(self, snapshot_id: str) -> int:
        return snapshot_count(
            self.client,
            self._bigquery,
            target_table=self.target_table,
            snapshot_id=snapshot_id,
        )

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str, parse_stats: dict[str, Any]) -> SlaughterLoadResult:
        self._validate_rows(rows, snapshot_id)
        started = datetime.now(timezone.utc)
        self.ensure_objects()
        status, persisted, existing = merge_snapshot_rows(
            self.client,
            self._bigquery,
            target_table=self.target_table,
            schema=self._schema(),
            rows=rows,
            snapshot_id=snapshot_id,
            stage_prefix="ibge_slaughter",
            started_at=started,
        )
        finished = datetime.now(timezone.utc)
        result = SlaughterLoadResult(
            status,
            snapshot_id,
            len(rows),
            persisted,
            existing,
            self.target_table,
            self.latest_view,
            self.quarterly_view,
            self.audit_table,
            started.isoformat(),
            finished.isoformat(),
        )
        write_domain_audit(
            self.client,
            audit_table=self.audit_table,
            error_label="IBGE Abate",
            row={
                "run_id": f"ibge_slaughter:{snapshot_id}:{started.isoformat()}",
                "source_id": "ibge_sidra_slaughter_1092",
                "domain": "pecuaria.slaughter",
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
            },
        )
        return result
