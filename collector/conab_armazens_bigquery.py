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
class LoadResult:
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


class ConabArmazensBigQueryLoader:
    """Carga idempotente por snapshot para CONAB Armazens.

    O alvo preserva todos os snapshots. Ausencia em um snapshot novo nao e tratada
    automaticamente como exclusao cadastral.
    """

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str = "logistica",
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
        self.target_table = f"{self.project_id}.{self.dataset_id}.armazens_conab"
        self.audit_table = f"{self.project_id}.{self.ops_dataset_id}.domain_load_runs"

    def _schema(self) -> list[Any]:
        field = self._bigquery.SchemaField
        return [
            field("snapshot_id", "STRING", mode="REQUIRED"),
            field("record_id", "STRING", mode="REQUIRED"),
            field("warehouse_id", "STRING", mode="REQUIRED"),
            field("source_id", "STRING", mode="REQUIRED"),
            field("cda", "STRING"), field("cnpj", "STRING"), field("razao_social", "STRING"),
            field("nome_armazem", "STRING"), field("endereco", "STRING"), field("bairro", "STRING"),
            field("cep", "STRING"), field("municipio", "STRING"), field("uf", "STRING"),
            field("codigo_ibge", "STRING"), field("tipo_armazenagem", "STRING"),
            field("capacidade_estatica_t", "FLOAT"), field("latitude", "FLOAT"), field("longitude", "FLOAT"),
            field("data_referencia", "DATE", mode="REQUIRED"), field("data_publicacao", "TIMESTAMP"),
            field("data_coleta", "TIMESTAMP", mode="REQUIRED"), field("competencia", "STRING", mode="REQUIRED"),
            field("evidence_class", "STRING", mode="REQUIRED"), field("raw_artifact_ref", "STRING"),
            field("source_url", "STRING"), field("source_hash", "STRING", mode="REQUIRED"),
            field("collector_version", "STRING"), field("quality_score", "FLOAT"),
            field("quality_flags", "STRING", mode="REPEATED"), field("source_payload_json", "STRING"),
        ]

    def ensure_objects(self) -> None:
        project = self.project_id
        location = self.location.replace("'", "")
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{project}.{self.dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{project}.{self.ops_dataset_id}` OPTIONS(location='{location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.target_table}` (
  snapshot_id STRING NOT NULL,
  record_id STRING NOT NULL,
  warehouse_id STRING NOT NULL,
  source_id STRING NOT NULL,
  cda STRING,
  cnpj STRING,
  razao_social STRING,
  nome_armazem STRING,
  endereco STRING,
  bairro STRING,
  cep STRING,
  municipio STRING,
  uf STRING,
  codigo_ibge STRING,
  tipo_armazenagem STRING,
  capacidade_estatica_t FLOAT64,
  latitude FLOAT64,
  longitude FLOAT64,
  data_referencia DATE NOT NULL,
  data_publicacao TIMESTAMP,
  data_coleta TIMESTAMP NOT NULL,
  competencia STRING NOT NULL,
  evidence_class STRING NOT NULL,
  raw_artifact_ref STRING,
  source_url STRING,
  source_hash STRING NOT NULL,
  collector_version STRING,
  quality_score FLOAT64,
  quality_flags ARRAY<STRING>,
  source_payload_json STRING
)
PARTITION BY data_referencia
CLUSTER BY uf, municipio, warehouse_id, snapshot_id
""").result()
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
CREATE OR REPLACE VIEW `{project}.{self.dataset_id}.v_armazens_conab_latest` AS
WITH latest AS (
  SELECT snapshot_id
  FROM `{self.target_table}`
  GROUP BY snapshot_id
  ORDER BY MAX(data_coleta) DESC
  LIMIT 1
)
SELECT *
FROM `{self.target_table}`
WHERE snapshot_id = (SELECT snapshot_id FROM latest)
""").result()

    def _snapshot_count(self, snapshot_id: str) -> int:
        config = self._bigquery.QueryJobConfig(
            query_parameters=[self._bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)]
        )
        rows = list(self.client.query(
            f"SELECT COUNT(*) AS n FROM `{self.target_table}` WHERE snapshot_id=@snapshot_id", job_config=config
        ).result())
        return int(rows[0]["n"]) if rows else 0

    def _write_audit(self, row: dict[str, Any]) -> None:
        errors = self.client.insert_rows_json(self.audit_table, [row])
        if errors:
            raise RuntimeError(f"Falha ao gravar auditoria da carga: {errors}")

    def load(
        self,
        rows: list[dict[str, Any]],
        *,
        snapshot_id: str,
        parse_stats: dict[str, Any],
        source_id: str = "conab_armazens_cadastrados",
    ) -> LoadResult:
        started = datetime.now(timezone.utc)
        self.ensure_objects()
        existing = self._snapshot_count(snapshot_id)
        run_id = f"{source_id}:{snapshot_id}:{started.isoformat()}"
        if existing:
            finished = datetime.now(timezone.utc)
            result = LoadResult(
                status="already_loaded", snapshot_id=snapshot_id, records_input=len(rows), records_inserted=0,
                records_existing=existing, target_table=self.target_table, audit_table=self.audit_table,
                started_at=started.isoformat(), finished_at=finished.isoformat(),
            )
            self._write_audit({
                "run_id": run_id, "source_id": source_id, "domain": "logistica.armazens",
                "target_table": self.target_table, "snapshot_id": snapshot_id, "status": result.status,
                "records_read": parse_stats.get("records_read"), "records_accepted": parse_stats.get("records_accepted"),
                "records_rejected": parse_stats.get("records_rejected"),
                "duplicates_removed": parse_stats.get("duplicates_removed"), "records_inserted": 0,
                "started_at": started.isoformat(), "finished_at": finished.isoformat(),
                "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
            })
            return result

        stage_name = f"armazens_conab_stage_{snapshot_id[:16]}_{int(started.timestamp())}"
        stage_ref = f"{self.project_id}.{self.dataset_id}.{stage_name}"
        table = self._bigquery.Table(stage_ref, schema=self._schema())
        table.expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.client.create_table(table)
        inserted = 0
        try:
            job_config = self._bigquery.LoadJobConfig(schema=self._schema(), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage_ref, job_config=job_config).result()
            self.client.query(f"""
MERGE `{self.target_table}` T
USING `{stage_ref}` S
ON T.snapshot_id = S.snapshot_id AND T.record_id = S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
            inserted = self._snapshot_count(snapshot_id)
        finally:
            self.client.delete_table(stage_ref, not_found_ok=True)

        finished = datetime.now(timezone.utc)
        result = LoadResult(
            status="loaded", snapshot_id=snapshot_id, records_input=len(rows), records_inserted=inserted,
            records_existing=0, target_table=self.target_table, audit_table=self.audit_table,
            started_at=started.isoformat(), finished_at=finished.isoformat(),
        )
        self._write_audit({
            "run_id": run_id, "source_id": source_id, "domain": "logistica.armazens",
            "target_table": self.target_table, "snapshot_id": snapshot_id, "status": result.status,
            "records_read": parse_stats.get("records_read"), "records_accepted": parse_stats.get("records_accepted"),
            "records_rejected": parse_stats.get("records_rejected"),
            "duplicates_removed": parse_stats.get("duplicates_removed"), "records_inserted": inserted,
            "started_at": started.isoformat(), "finished_at": finished.isoformat(),
            "details_json": json.dumps(parse_stats, ensure_ascii=False, sort_keys=True),
        })
        return result
