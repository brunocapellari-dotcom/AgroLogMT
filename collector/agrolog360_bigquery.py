from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def stable_record_id(parts: Iterable[object]) -> str:
    text = "|".join("" if value is None else str(value).strip() for value in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CanonicalLoadResult:
    status: str
    target_table: str
    rows_input: int
    rows_inserted: int
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TABLES = {
    "climate": {
        "dataset": "clima",
        "table": "daily_observations",
        "cluster": "source_id, geo_id, competencia",
        "columns": ("record_id","source_id","geo_id","data_referencia","data_publicacao","data_coleta","competencia","precipitacao_mm","tmin_c","tmax_c","evidence_class","quality_flags"),
        "ddl": """
record_id STRING NOT NULL,
source_id STRING NOT NULL,
geo_id STRING NOT NULL,
data_referencia DATE NOT NULL,
data_publicacao TIMESTAMP,
data_coleta TIMESTAMP NOT NULL,
competencia STRING NOT NULL,
precipitacao_mm FLOAT64,
tmin_c FLOAT64,
tmax_c FLOAT64,
evidence_class STRING NOT NULL,
quality_flags ARRAY<STRING>
""".strip(),
    },
    "freight": {
        "dataset": "logistica",
        "table": "freight_offer_observations",
        "cluster": "origin_municipality_id, destination_municipality_id, product_id",
        "columns": ("record_id","observation_id","source_channel_type","source_provider","source_channel_id_hash","source_message_id_hash","origin_municipality_id","destination_municipality_id","product_id","freight_brl_per_t","freight_brl_per_t_km","announced_brl_per_trip","distance_km","payload_t","dedup_cluster_id","requires_review","data_referencia","data_publicacao","data_coleta","competencia","evidence_class","evidence_subtype","contracted_status","executed_status"),
        "ddl": """
record_id STRING NOT NULL,
observation_id STRING NOT NULL,
source_channel_type STRING NOT NULL,
source_provider STRING NOT NULL,
source_channel_id_hash STRING NOT NULL,
source_message_id_hash STRING NOT NULL,
origin_municipality_id STRING,
destination_municipality_id STRING,
product_id STRING,
freight_brl_per_t FLOAT64,
freight_brl_per_t_km FLOAT64,
announced_brl_per_trip FLOAT64,
distance_km FLOAT64,
payload_t FLOAT64,
dedup_cluster_id STRING NOT NULL,
requires_review BOOL NOT NULL,
data_referencia DATE NOT NULL,
data_publicacao TIMESTAMP NOT NULL,
data_coleta TIMESTAMP NOT NULL,
competencia STRING NOT NULL,
evidence_class STRING NOT NULL,
evidence_subtype STRING NOT NULL,
contracted_status STRING NOT NULL,
executed_status STRING NOT NULL
""".strip(),
    },
    "biomass": {
        "dataset": "energia",
        "table": "biomass_observations",
        "cluster": "source_id, geo_id, biomass_type, metric_id",
        "columns": ("record_id","source_id","geo_id","biomass_type","metric_id","value","unit","data_referencia","data_publicacao","data_coleta","competencia","evidence_class","observation_semantics","source_quality","quality_flags"),
        "ddl": """
record_id STRING NOT NULL,
source_id STRING NOT NULL,
geo_id STRING NOT NULL,
biomass_type STRING NOT NULL,
metric_id STRING NOT NULL,
value FLOAT64 NOT NULL,
unit STRING NOT NULL,
data_referencia DATE NOT NULL,
data_publicacao TIMESTAMP,
data_coleta TIMESTAMP NOT NULL,
competencia STRING NOT NULL,
evidence_class STRING NOT NULL,
observation_semantics STRING NOT NULL,
source_quality STRING NOT NULL,
quality_flags ARRAY<STRING>
""".strip(),
    },
}


def table_ddl(project_id: str, kind: str, *, location: str = "southamerica-east1") -> tuple[str, str]:
    project = _safe(project_id, "project_id")
    if kind not in TABLES:
        raise ValueError(f"kind inválido: {kind}")
    spec = TABLES[kind]
    dataset = _safe(spec["dataset"], "dataset")
    table = _safe(spec["table"], "table")
    safe_location = location.replace("'", "")
    dataset_sql = f"CREATE SCHEMA IF NOT EXISTS `{project}.{dataset}` OPTIONS(location='{safe_location}')"
    table_sql = f"""CREATE TABLE IF NOT EXISTS `{project}.{dataset}.{table}` (
{spec['ddl']}
)
PARTITION BY data_referencia
CLUSTER BY {spec['cluster']}
""".strip()
    return dataset_sql, table_sql


class AgroLog360BigQueryLoader:
    def __init__(
        self,
        *,
        project_id: str,
        location: str = "southamerica-east1",
        client: Any | None = None,
    ) -> None:
        self.project_id = _safe(project_id, "project_id")
        self.location = location
        from google.cloud import bigquery

        self._bigquery = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)

    def _target(self, kind: str) -> str:
        spec = TABLES[kind]
        return f"{self.project_id}.{spec['dataset']}.{spec['table']}"

    def _prepare(self, kind: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            raise ValueError("carga vazia não cria dataset/tabela")
        prepared: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            if kind == "climate":
                row["record_id"] = row.get("record_id") or stable_record_id([
                    row.get("source_id"), row.get("geo_id"), row.get("data_referencia")
                ])
            elif kind == "freight":
                row["record_id"] = row.get("record_id") or row.get("observation_id")
                if not row["record_id"]:
                    raise ValueError("freight observation_id obrigatório")
            elif kind == "biomass":
                row["record_id"] = row.get("record_id") or stable_record_id([
                    row.get("source_id"), row.get("geo_id"), row.get("biomass_type"),
                    row.get("metric_id"), row.get("data_referencia"), row.get("value"), row.get("unit"),
                ])
            prepared.append(row)
        return prepared

    def load(self, kind: str, rows: list[dict[str, Any]]) -> CanonicalLoadResult:
        if kind not in TABLES:
            raise ValueError(f"kind inválido: {kind}")
        prepared = self._prepare(kind, rows)
        started = datetime.now(timezone.utc)
        dataset_sql, table_sql = table_ddl(self.project_id, kind, location=self.location)
        self.client.query(dataset_sql).result()
        self.client.query(table_sql).result()

        target = self._target(kind)
        stage = f"{target}_stage_{int(started.timestamp())}"
        target_obj = self.client.get_table(target)
        table = self._bigquery.Table(stage, schema=target_obj.schema)
        table.expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.client.create_table(table)
        try:
            config = self._bigquery.LoadJobConfig(
                schema=target_obj.schema,
                write_disposition="WRITE_TRUNCATE",
            )
            self.client.load_table_from_json(prepared, stage, job_config=config).result()
            columns = tuple(TABLES[kind]["columns"])
            insert_columns = ", ".join(columns)
            insert_values = ", ".join(f"S.{column}" for column in columns)
            merge = f"""
MERGE `{target}` T
USING `{stage}` S
ON T.record_id=S.record_id
WHEN NOT MATCHED THEN
  INSERT ({insert_columns}) VALUES ({insert_values})
""".strip()
            job = self.client.query(merge)
            job.result()
            inserted = int(getattr(job, "num_dml_affected_rows", 0) or 0)
        finally:
            self.client.delete_table(stage, not_found_ok=True)

        finished = datetime.now(timezone.utc)
        return CanonicalLoadResult(
            status="loaded",
            target_table=target,
            rows_input=len(prepared),
            rows_inserted=inserted,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
        )
