from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def _expected_snapshot_records(rows: list[dict[str, Any]], snapshot_id: str) -> tuple[int, int]:
    if not rows:
        raise ValueError("CONAB Safra loader recusou lote vazio")
    record_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if row.get("snapshot_id") != snapshot_id:
            raise ValueError(f"CONAB Safra snapshot_id divergente na linha {index}")
        record_id = row.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"CONAB Safra record_id inválido na linha {index}")
        record_ids.add(record_id)
    return len(record_ids), len(rows) - len(record_ids)


@dataclass(frozen=True)
class SafraLoadResult:
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


class ConabSafraBigQueryLoader:
    """Loader point-in-time idempotente para vintages oficiais da CONAB Safra."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "agro",
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
        self.target_table = f"{self.project_id}.{self.dataset_id}.conab_safra_graos"
        self.audit_table = f"{self.project_id}.{self.ops_dataset_id}.domain_load_runs"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("source_id", "STRING", mode="REQUIRED"),
            field("geo_level", "STRING", mode="REQUIRED"),
            field("geo_id", "STRING", mode="REQUIRED"),
            field("produto_origem", "STRING", mode="REQUIRED"),
            field("product_id", "STRING", mode="REQUIRED"),
            field("safra", "STRING", mode="REQUIRED"),
            field("vintage_position", "STRING", mode="REQUIRED"),
            field("area_mil_ha", "FLOAT", mode="REQUIRED"),
            field("produtividade_kg_ha", "FLOAT", mode="REQUIRED"),
            field("producao_mil_t", "FLOAT", mode="REQUIRED"),
            field("area_var_pct", "FLOAT"),
            field("produtividade_var_pct", "FLOAT"),
            field("producao_var_pct", "FLOAT"),
            field("identity_error_mil_t", "FLOAT"),
            field("identity_error_pct", "FLOAT"),
            field("data_referencia", "DATE", mode="REQUIRED"),
            field("data_publicacao", "TIMESTAMP", mode="REQUIRED"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"),
            field("data_disponibilidade", "TIMESTAMP"),
            field("availability_verified", "BOOL", mode="REQUIRED"),
            field("availability_basis", "STRING"),
            field("competencia", "STRING", mode="REQUIRED"),
            field("evidence_class", "STRING", mode="REQUIRED"),
            field("methodology_id", "STRING", mode="REQUIRED"),
            field("raw_artifact_ref", "STRING"),
            field("source_url", "STRING"),
            field("source_hash", "STRING", mode="REQUIRED"),
            field("collector_version", "STRING"),
            field("parser_version", "STRING"),
            field("quality_score", "FLOAT"),
            field("quality_flags", "STRING", mode="REPEATED"),
            field("source_sheet", "STRING"),
            field("source_row", "INT64"),
        ]

    def ensure_objects(self) -> None:
        location = self.location.replace("'", "")
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.ops_dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  source_id STRING NOT NULL,
  geo_level STRING NOT NULL,
  geo_id STRING NOT NULL,
  produto_origem STRING NOT NULL,
  product_id STRING NOT NULL,
  safra STRING NOT NULL,
  vintage_position STRING NOT NULL,
  area_mil_ha FLOAT64 NOT NULL,
  produtividade_kg_ha FLOAT64 NOT NULL,
  producao_mil_t FLOAT64 NOT NULL,
  area_var_pct FLOAT64,
  produtividade_var_pct FLOAT64,
  producao_var_pct FLOAT64,
  identity_error_mil_t FLOAT64,
  identity_error_pct FLOAT64,
  data_referencia DATE NOT NULL,
  data_publicacao TIMESTAMP NOT NULL,
  data_coleta TIMESTAMP NOT NULL,
  data_disponibilidade TIMESTAMP,
  availability_verified BOOL NOT NULL,
  availability_basis STRING,
  competencia STRING NOT NULL,
  evidence_class STRING NOT NULL,
  methodology_id STRING NOT NULL,
  raw_artifact_ref STRING,
  source_url STRING,
  source_hash STRING NOT NULL,
  collector_version STRING,
  parser_version STRING,
  quality_score FLOAT64,
  quality_flags ARRAY<STRING>,
  source_sheet STRING,
  source_row INT64
)
PARTITION BY data_referencia
CLUSTER BY product_id, geo_id, safra, snapshot_id
""").result()
        # Migração aditiva segura para tabelas criadas antes do metadata v1.2.
        self.client.query(f"ALTER TABLE `{self.target_table}` ADD COLUMN IF NOT EXISTS data_disponibilidade TIMESTAMP").result()
        self.client.query(f"ALTER TABLE `{self.target_table}` ADD COLUMN IF NOT EXISTS availability_verified BOOL").result()
        self.client.query(f"ALTER TABLE `{self.target_table}` ADD COLUMN IF NOT EXISTS availability_basis STRING").result()
        self.client.query(f"""
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
""").result()
        self.client.query(f"""
CREATE OR REPLACE VIEW `{self.project_id}.{self.dataset_id}.v_conab_safra_latest` AS
WITH latest AS (
  SELECT snapshot_id
  FROM `{self.target_table}`
  GROUP BY snapshot_id
  ORDER BY MAX(data_coleta) DESC
  LIMIT 1
)
SELECT * FROM `{self.target_table}`
WHERE snapshot_id=(SELECT snapshot_id FROM latest)
""").result()

    def _snapshot_count(self, snapshot_id: str) -> int:
        config = self._bigquery.QueryJobConfig(query_parameters=[
            self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)
        ])
        rows = list(self.client.query(
            f"SELECT COUNT(*) AS n FROM `{self.target_table}` WHERE snapshot_id=@snapshot_id", job_config=config
        ).result())
        return int(rows[0]["n"]) if rows else 0

    @staticmethod
    def _assert_snapshot_count(expected: int, actual: int, *, snapshot_id: str) -> None:
        if actual != expected:
            raise RuntimeError(
                "Tie-out CONAB Safra falhou: "
                f"snapshot={snapshot_id} esperado={expected} persistido={actual}"
            )

    def _write_audit(self, row: dict[str, Any]) -> None:
        errors = self.client.insert_rows_json(self.audit_table, [row])
        if errors:
            raise RuntimeError(f"Falha ao gravar auditoria CONAB Safra: {errors}")

    def load(self, rows: list[dict[str, Any]], *, snapshot_id: str, parse_stats: dict[str, Any]) -> SafraLoadResult:
        started = datetime.now(timezone.utc)
        expected, duplicates_removed = _expected_snapshot_records(rows, snapshot_id)
        self.ensure_objects()
        existing = self._snapshot_count(snapshot_id)
        run_id = f"conab_safra:{snapshot_id}:{started.isoformat()}"
        if existing:
            self._assert_snapshot_count(expected, existing, snapshot_id=snapshot_id)
            finished = datetime.now(timezone.utc)
            result = SafraLoadResult(
                status="already_loaded", snapshot_id=snapshot_id, records_input=len(rows), records_inserted=0,
                records_existing=existing, target_table=self.target_table, audit_table=self.audit_table,
                started_at=started.isoformat(), finished_at=finished.isoformat(),
            )
            self._write_audit({
                "run_id": run_id, "source_id": "conab_safra_graos_xlsx", "domain": "agro.safra",
                "target_table": self.target_table, "snapshot_id": snapshot_id, "status": result.status,
                "records_read": parse_stats.get("records_read"), "records_accepted": parse_stats.get("records_accepted"),
                "records_rejected": parse_stats.get("records_rejected", 0), "duplicates_removed": duplicates_removed,
                "records_inserted": 0, "started_at": started.isoformat(), "finished_at": finished.isoformat(),
                "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
            })
            return result

        stage_ref = f"{self.project_id}.{self.dataset_id}.conab_safra_stage_{snapshot_id[:12]}_{int(started.timestamp())}"
        table = self._bigquery.Table(stage_ref, schema=self._schema())
        table.expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.client.create_table(table)
        try:
            job_config = self._bigquery.LoadJobConfig(schema=self._schema(), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage_ref, job_config=job_config).result()
            self.client.query(f"""
MERGE `{self.target_table}` T
USING (
  SELECT * EXCEPT(_rn) FROM (
    SELECT S.*, ROW_NUMBER() OVER(PARTITION BY snapshot_id, record_id ORDER BY record_id) AS _rn
    FROM `{stage_ref}` S
  ) WHERE _rn=1
) S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)

        inserted = self._snapshot_count(snapshot_id)
        self._assert_snapshot_count(expected, inserted, snapshot_id=snapshot_id)
        finished = datetime.now(timezone.utc)
        result = SafraLoadResult(
            status="loaded", snapshot_id=snapshot_id, records_input=len(rows), records_inserted=inserted,
            records_existing=0, target_table=self.target_table, audit_table=self.audit_table,
            started_at=started.isoformat(), finished_at=finished.isoformat(),
        )
        self._write_audit({
            "run_id": run_id, "source_id": "conab_safra_graos_xlsx", "domain": "agro.safra",
            "target_table": self.target_table, "snapshot_id": snapshot_id, "status": result.status,
            "records_read": parse_stats.get("records_read"), "records_accepted": parse_stats.get("records_accepted"),
            "records_rejected": parse_stats.get("records_rejected", 0), "duplicates_removed": duplicates_removed,
            "records_inserted": inserted, "started_at": started.isoformat(), "finished_at": finished.isoformat(),
            "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
        })
        return result
