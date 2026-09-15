from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def _expected_group_records(rows: list[dict[str, Any]], snapshot_id: str) -> tuple[int, int]:
    if not rows:
        return 0, 0
    record_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if row.get("snapshot_id") != snapshot_id:
            raise ValueError(f"IMEA snapshot_id divergente na linha {index}")
        record_id = row.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"IMEA record_id inválido na linha {index}")
        record_ids.add(record_id)
    return len(record_ids), len(rows) - len(record_ids)


class ImeaOperationalBigQueryLoader:
    def __init__(self, *, project_id: str, location: str = "southamerica-east1", client: Any | None = None) -> None:
        self.project_id = _safe_identifier(project_id, "project_id")
        self.location = location
        from google.cloud import bigquery
        self.bq = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=location)
        self.indicators = f"{self.project_id}.mercado.imea_indicadores_operacionais"
        self.freight = f"{self.project_id}.logistica.imea_frete_referencia"
        self.progress = f"{self.project_id}.agro.imea_progresso_cultura"

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

    @staticmethod
    def _assert_group_count(expected: int, actual: int, *, table: str, snapshot_id: str) -> None:
        if actual != expected:
            raise RuntimeError(
                "Tie-out IMEA falhou: "
                f"table={table} snapshot={snapshot_id} esperado={expected} persistido={actual}"
            )

    def _load_group(self, table: str, kind: str, rows: list[dict[str, Any]], snapshot_id: str) -> dict[str, Any]:
        if not rows:
            return {"status": "empty", "records_inserted": 0, "records_expected": 0, "records_input": 0}
        expected, duplicates_removed = _expected_group_records(rows, snapshot_id)
        existing = self._existing(table, snapshot_id)
        if existing:
            self._assert_group_count(expected, existing, table=table, snapshot_id=snapshot_id)
            return {
                "status": "already_loaded",
                "records_inserted": 0,
                "records_existing": existing,
                "records_expected": expected,
                "records_input": len(rows),
                "duplicates_removed": duplicates_removed,
            }
        started = datetime.now(timezone.utc)
        stage = f"{table.rsplit('.',1)[0]}._stg_imea_{kind}_{snapshot_id[:10]}_{int(started.timestamp())}"
        obj = self.bq.Table(stage, schema=self._schema(kind)); obj.expires = started + timedelta(hours=2)
        self.client.create_table(obj)
        try:
            cfg = self.bq.LoadJobConfig(schema=self._schema(kind), write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage, job_config=cfg).result()
            self.client.query(f"""
MERGE `{table}` T
USING (
  SELECT * EXCEPT(_rn) FROM (
    SELECT S.*, ROW_NUMBER() OVER(PARTITION BY snapshot_id, record_id ORDER BY record_id) AS _rn
    FROM `{stage}` S
  ) WHERE _rn=1
) S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage, not_found_ok=True)
        inserted = self._existing(table, snapshot_id)
        self._assert_group_count(expected, inserted, table=table, snapshot_id=snapshot_id)
        return {
            "status": "loaded",
            "records_inserted": inserted,
            "records_existing": 0,
            "records_expected": expected,
            "records_input": len(rows),
            "duplicates_removed": duplicates_removed,
        }

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
