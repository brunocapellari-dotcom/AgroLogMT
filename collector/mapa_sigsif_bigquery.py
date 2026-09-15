from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .mapa_sigsif import FEMALE_METRIC, MALE_METRIC, SOURCE_ID
from .snapshot_bigquery import (
    ensure_dataset,
    ensure_domain_audit_table,
    merge_snapshot_rows,
    safe_identifier,
    write_domain_audit,
)


@dataclass(frozen=True)
class SigsifLoadResult:
    status: str
    snapshot_id: str
    records_input: int
    records_persisted: int
    records_existing: int
    target_table: str
    latest_view: str
    summary_view: str
    audit_table: str
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MapaSigsifBigQueryLoader:
    """Persist current SIGSIF SIF snapshot without inventing an event period."""

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
        self.target_table = f"{self.project_id}.{self.dataset_id}.mapa_sigsif_slaughter_snapshot_mt"
        self.latest_view = f"{self.project_id}.{self.dataset_id}.v_mapa_sigsif_slaughter_snapshot_mt_latest"
        self.summary_view = f"{self.project_id}.{self.dataset_id}.v_mapa_sigsif_slaughter_snapshot_mt_summary"
        self.audit_table = f"{self.project_id}.{self.ops_dataset_id}.domain_load_runs"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("source_id", "STRING", mode="REQUIRED"),
            field("geo_level", "STRING", mode="REQUIRED"),
            field("geo_id", "STRING", mode="REQUIRED"),
            field("product_id", "STRING", mode="REQUIRED"),
            field("sex", "STRING", mode="REQUIRED"),
            field("metric_id", "STRING", mode="REQUIRED"),
            field("value", "INT64", mode="REQUIRED"),
            field("unit", "STRING", mode="REQUIRED"),
            field("snapshot_date", "DATE", mode="REQUIRED"),
            field("data_referencia", "DATE", mode="REQUIRED"),
            field("data_publicacao", "TIMESTAMP"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("data_disponibilidade", "TIMESTAMP", mode="REQUIRED"),
            field("availability_verified", "BOOL", mode="REQUIRED"),
            field("availability_basis", "STRING", mode="REQUIRED"),
            field("point_in_time_feature_eligible", "BOOL", mode="REQUIRED"),
            field("target_role", "STRING", mode="REQUIRED"),
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
  product_id STRING NOT NULL,
  sex STRING NOT NULL,
  metric_id STRING NOT NULL,
  value INT64 NOT NULL,
  unit STRING NOT NULL,
  snapshot_date DATE NOT NULL,
  data_referencia DATE NOT NULL,
  data_publicacao TIMESTAMP,
  data_coleta TIMESTAMP NOT NULL,
  data_disponibilidade TIMESTAMP NOT NULL,
  availability_verified BOOL NOT NULL,
  availability_basis STRING NOT NULL,
  point_in_time_feature_eligible BOOL NOT NULL,
  target_role STRING NOT NULL,
  evidence_class STRING NOT NULL,
  methodology_id STRING NOT NULL,
  raw_artifact_ref STRING,
  source_url STRING NOT NULL,
  source_hash STRING NOT NULL,
  collector_version STRING,
  quality_score FLOAT64,
  quality_flags ARRAY<STRING>
)
PARTITION BY snapshot_date
CLUSTER BY sex, snapshot_id
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.latest_view}` AS
SELECT * EXCEPT(rn)
FROM (
  SELECT *, ROW_NUMBER() OVER(
    PARTITION BY sex
    ORDER BY data_coleta DESC, snapshot_id DESC
  ) rn
  FROM `{self.target_table}`
)
WHERE rn=1
"""
        ).result()
        self.client.query(
            f"""
CREATE OR REPLACE VIEW `{self.summary_view}` AS
WITH latest AS (
  SELECT
    MAX(snapshot_date) AS snapshot_date,
    MAX(data_coleta) AS data_coleta,
    MAX(IF(metric_id='{MALE_METRIC}', value, NULL)) AS machos,
    MAX(IF(metric_id='{FEMALE_METRIC}', value, NULL)) AS femeas
  FROM `{self.latest_view}`
)
SELECT
  *,
  COALESCE(machos, 0) + COALESCE(femeas, 0) AS total_bovinos,
  SAFE_DIVIDE(femeas, COALESCE(machos, 0) + COALESCE(femeas, 0)) AS participacao_femeas,
  'snapshot_collection_date_not_event_period' AS temporal_semantics
FROM latest
"""
        ).result()

    @staticmethod
    def _validate_rows(rows: list[dict[str, Any]], snapshot_id: str) -> None:
        if len(rows) != 2:
            raise ValueError("SIGSIF snapshot deve conter exatamente macho e femea")
        metrics = {str(row.get("metric_id") or "") for row in rows}
        sexes = {str(row.get("sex") or "") for row in rows}
        if metrics != {MALE_METRIC, FEMALE_METRIC} or sexes != {"macho", "femea"}:
            raise ValueError("SIGSIF snapshot fora do contrato macho/femea")
        ids: set[str] = set()
        for row in rows:
            if row.get("snapshot_id") != snapshot_id:
                raise ValueError("SIGSIF snapshot_id inconsistente")
            if row.get("point_in_time_feature_eligible") is not False:
                raise ValueError("SIGSIF sem período interno não pode ser feature point-in-time")
            if row.get("target_role") != "current_sif_crosscheck_not_historical_flow":
                raise ValueError("SIGSIF target_role inconsistente")
            record_id = str(row.get("record_id") or "")
            if not record_id or record_id in ids:
                raise ValueError("SIGSIF record_id ausente ou duplicado")
            ids.add(record_id)
            if int(row.get("value") or 0) < 0:
                raise ValueError("SIGSIF valor negativo")

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str, parse_stats: dict[str, Any]) -> SigsifLoadResult:
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
            stage_prefix="mapa_sigsif",
            started_at=started,
        )
        finished = datetime.now(timezone.utc)
        result = SigsifLoadResult(
            status,
            snapshot_id,
            len(rows),
            persisted,
            existing,
            self.target_table,
            self.latest_view,
            self.summary_view,
            self.audit_table,
            started.isoformat(),
            finished.isoformat(),
        )
        write_domain_audit(
            self.client,
            audit_table=self.audit_table,
            error_label="MAPA SIGSIF",
            row={
                "run_id": f"mapa_sigsif:{snapshot_id}:{started.isoformat()}",
                "source_id": SOURCE_ID,
                "domain": "pecuaria.slaughter_crosscheck",
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
