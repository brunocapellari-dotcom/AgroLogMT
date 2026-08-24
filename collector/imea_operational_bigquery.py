from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class ImeaOperationalBigQueryLoader:
    def __init__(self, *, project_id: str, location: str = "southamerica-east1", client: Any | None = None) -> None:
        self.project_id = project_id
        self.location = location
        from google.cloud import bigquery
        self.bq = bigquery
        self.client = client or bigquery.Client(project=project_id, location=location)
        self.indicators = f"{project_id}.mercado.imea_indicadores_operacionais"
        self.freight = f"{project_id}.logistica.imea_frete_referencia"
        self.progress = f"{project_id}.agro.imea_progresso_cultura"

    def ensure_objects(self) -> None:
        for dataset in ("mercado", "logistica", "agro"):
            self.client.query(
                f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{dataset}` OPTIONS(location='{self.location}')"
            ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.indicators}` (
 snapshot_id STRING NOT NULL, record_id STRING NOT NULL, source_sheet STRING NOT NULL,
 data_referencia DATE NOT NULL, produto STRING NOT NULL, metric_name STRING NOT NULL,
 valor FLOAT64 NOT NULL, unidade_origem STRING, unidade_canonica STRING, local STRING,
 evidence_class STRING NOT NULL, evidence_subtype STRING NOT NULL, negotiated BOOL NOT NULL,
 data_coleta TIMESTAMP NOT NULL, source_hash STRING NOT NULL, raw_artifact_ref STRING
) PARTITION BY data_referencia CLUSTER BY produto, metric_name, local, snapshot_id
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.freight}` (
 snapshot_id STRING NOT NULL, record_id STRING NOT NULL, data_referencia DATE NOT NULL,
 produto STRING NOT NULL, metric_name STRING NOT NULL, origem STRING NOT NULL, destino STRING NOT NULL,
 valor FLOAT64 NOT NULL, unidade_origem STRING, unidade_canonica STRING,
 evidence_class STRING NOT NULL, evidence_subtype STRING NOT NULL, negotiated BOOL NOT NULL,
 data_coleta TIMESTAMP NOT NULL, source_hash STRING NOT NULL, raw_artifact_ref STRING
) PARTITION BY data_referencia CLUSTER BY produto, origem, destino, snapshot_id
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.progress}` (
 snapshot_id STRING NOT NULL, record_id STRING NOT NULL, source_sheet STRING NOT NULL,
 data_referencia DATE NOT NULL, produto STRING NOT NULL, safra STRING NOT NULL, regiao STRING NOT NULL,
 metric_name STRING NOT NULL, valor FLOAT64 NOT NULL, unidade_canonica STRING NOT NULL,
 evidence_class STRING NOT NULL, evidence_subtype STRING NOT NULL,
 data_coleta TIMESTAMP NOT NULL, source_hash STRING NOT NULL, raw_artifact_ref STRING
) PARTITION BY data_referencia CLUSTER BY produto, safra, regiao, source_sheet
""").result()

    def _schema(self, kind: str) -> list[Any]:
        f = self.bq.SchemaField
        common_tail = [
            f("data_coleta", "TIMESTAMP", mode="REQUIRED"), f("source_hash", "STRING", mode="REQUIRED"),
            f("raw_artifact_ref", "STRING"),
        ]
        if kind == "indicator":
            return [f("snapshot_id","STRING","REQUIRED"), f("record_id","STRING","REQUIRED"), f("source_sheet","STRING","REQUIRED"),
                    f("data_referencia","DATE","REQUIRED"), f("produto","STRING","REQUIRED"), f("metric_name","STRING","REQUIRED"),
                    f("valor","FLOAT","REQUIRED"), f("unidade_origem","STRING"), f("unidade_canonica","STRING"), f("local","STRING"),
                    f("evidence_class","STRING","REQUIRED"), f("evidence_subtype","STRING","REQUIRED"), f("negotiated","BOOL","REQUIRED"), *common_tail]
        if kind == "freight":
            return [f("snapshot_id","STRING","REQUIRED"), f("record_id","STRING","REQUIRED"), f("data_referencia","DATE","REQUIRED"),
                    f("produto","STRING","REQUIRED"), f("metric_name","STRING","REQUIRED"), f("origem","STRING","REQUIRED"), f("destino","STRING","REQUIRED"),
                    f("valor","FLOAT","REQUIRED"), f("unidade_origem","STRING"), f("unidade_canonica","STRING"),
                    f("evidence_class","STRING","REQUIRED"), f("evidence_subtype","STRING","REQUIRED"), f("negotiated","BOOL","REQUIRED"), *common_tail]
        return [f("snapshot_id","STRING","REQUIRED"), f("record_id","STRING","REQUIRED"), f("source_sheet","STRING","REQUIRED"),
                f("data_referencia","DATE","REQUIRED"), f("produto","STRING","REQUIRED"), f("safra","STRING","REQUIRED"), f("regiao","STRING","REQUIRED"),
                f("metric_name","STRING","REQUIRED"), f("valor","FLOAT","REQUIRED"), f("unidade_canonica","STRING","REQUIRED"),
                f("evidence_class","STRING","REQUIRED"), f("evidence_subtype","STRING","REQUIRED"), *common_tail]

    def _existing(self, table: str, snapshot_id: str) -> int:
        cfg = self.bq.QueryJobConfig(query_parameters=[self.bq.ScalarQueryParameter("snapshot", "STRING", snapshot_id)])
        rows = list(self.client.query(f"SELECT COUNT(*) n FROM `{table}` WHERE snapshot_id=@snapshot", job_config=cfg).result())
        return int(rows[0]["n"]) if rows else 0

    def _load_group(self, table: str, kind: str, rows: list[dict[str, Any]], snapshot_id: str) -> dict[str, Any]:
        if not rows:
            return {"status": "empty", "records_inserted": 0}
        existing = self._existing(table, snapshot_id)
        if existing:
            return {"status": "already_loaded", "records_inserted": 0, "records_existing": existing}
        started = datetime.now(timezone.utc)
        stage = f"{table.rsplit('.',1)[0]}._stg_imea_{kind}_{snapshot_id[:10]}_{int(started.timestamp())}"
        obj = self.bq.Table(stage, schema=self._schema(kind)); obj.expires = started + timedelta(hours=2)
        self.client.create_table(obj)
        try:
            cfg = self.bq.LoadJobConfig(schema=self._schema(kind), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage, job_config=cfg).result()
            self.client.query(f"MERGE `{table}` T USING `{stage}` S ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id WHEN NOT MATCHED THEN INSERT ROW").result()
        finally:
            self.client.delete_table(stage, not_found_ok=True)
        return {"status": "loaded", "records_inserted": self._existing(table, snapshot_id)}

    def load(self, parsed: dict[str, Any], *, snapshot_id: str, data_coleta: str, source_hash: str, raw_artifact_ref: str | None) -> dict[str, Any]:
        self.ensure_objects()
        indicator_rows: list[dict[str, Any]] = []
        freight_rows: list[dict[str, Any]] = []
        progress_rows: list[dict[str, Any]] = []
        for source in parsed["records"]:
            common = {"snapshot_id": snapshot_id, "data_coleta": data_coleta, "source_hash": source_hash, "raw_artifact_ref": raw_artifact_ref}
            sheet = source["source_sheet"]
            if sheet in {"indicadores diarios", "indicadores semanais"}:
                indicator_rows.append({k: source.get(k) for k in ("record_id","source_sheet","data_referencia","produto","metric_name","valor","unidade_origem","unidade_canonica","local","evidence_class","evidence_subtype","negotiated")} | common)
            elif sheet == "frete":
                freight_rows.append({k: source.get(k) for k in ("record_id","data_referencia","produto","metric_name","origem","destino","valor","unidade_origem","unidade_canonica","evidence_class","evidence_subtype","negotiated")} | common)
            else:
                progress_rows.append({k: source.get(k) for k in ("record_id","source_sheet","data_referencia","produto","safra","regiao","metric_name","valor","unidade_canonica","evidence_class","evidence_subtype")} | common)
        return {
            "indicators": self._load_group(self.indicators, "indicator", indicator_rows, snapshot_id),
            "freight": self._load_group(self.freight, "freight", freight_rows, snapshot_id),
            "progress": self._load_group(self.progress, "progress", progress_rows, snapshot_id),
        }
