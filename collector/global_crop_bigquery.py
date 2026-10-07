from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .argentina_estimaciones import ArgentinaCropRecord
from .usda_wasde import WasdeArtifact, WasdeCell, artifact_hash

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def _stable_hash(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class ArgentinaCropBigQueryLoader:
    def __init__(self, *, project_id: str, location: str = "southamerica-east1", client: Any | None = None) -> None:
        from google.cloud import bigquery
        self.bq = bigquery
        self.project_id = _safe(project_id, "project_id")
        self.location = location
        self.client = client or bigquery.Client(project=self.project_id, location=location)
        self.table = f"{self.project_id}.agro.argentina_estimaciones"

    def ensure_objects(self) -> None:
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.agro` OPTIONS(location='{self.location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.table}` (
 snapshot_id STRING NOT NULL,
 record_id STRING NOT NULL,
 source_id STRING NOT NULL,
 crop STRING NOT NULL,
 crop_id STRING NOT NULL,
 reference_year INT64,
 season STRING NOT NULL,
 province STRING,
 province_id STRING,
 department STRING,
 department_id STRING,
 planted_area_ha FLOAT64,
 harvested_area_ha FLOAT64,
 production_t FLOAT64,
 yield_kg_ha FLOAT64,
 evidence_class STRING NOT NULL,
 source_url STRING,
 source_hash STRING NOT NULL,
 data_coleta TIMESTAMP NOT NULL,
 raw_artifact_ref STRING,
 source_updated_at TIMESTAMP
)
PARTITION BY DATE(data_coleta)
CLUSTER BY crop_id, season, province_id, snapshot_id
""").result()

    def load(
        self,
        records: list[ArgentinaCropRecord],
        *,
        snapshot_id: str,
        source_hash: str,
        data_coleta: str,
        source_url: str,
        raw_artifact_ref: str | None = None,
        source_updated_at: str | None = None,
    ) -> dict[str, Any]:
        if not records:
            raise ValueError("Argentina loader recusou lote vazio")
        self.ensure_objects()
        payload: list[dict[str, Any]] = []
        for row in records:
            natural = [
                row.crop_id, str(row.year or ""), row.season,
                row.province_id or row.province, row.department_id or row.department,
            ]
            payload.append({
                "snapshot_id": snapshot_id,
                "record_id": _stable_hash(natural),
                "source_id": row.source_id,
                "crop": row.crop,
                "crop_id": row.crop_id,
                "reference_year": row.year,
                "season": row.season,
                "province": row.province or None,
                "province_id": row.province_id,
                "department": row.department or None,
                "department_id": row.department_id,
                "planted_area_ha": row.planted_area_ha,
                "harvested_area_ha": row.harvested_area_ha,
                "production_t": row.production_t,
                "yield_kg_ha": row.yield_kg_ha,
                "evidence_class": row.evidence_class,
                "source_url": source_url,
                "source_hash": source_hash,
                "data_coleta": data_coleta,
                "raw_artifact_ref": raw_artifact_ref,
                "source_updated_at": source_updated_at,
            })

        expected = len({row["record_id"] for row in payload})
        stage = f"{self.project_id}.agro._stg_argentina_{int(datetime.now(timezone.utc).timestamp())}"
        schema = [self.bq.SchemaField(name, typ, mode=mode) for name, typ, mode in (
            ("snapshot_id","STRING","REQUIRED"), ("record_id","STRING","REQUIRED"), ("source_id","STRING","REQUIRED"),
            ("crop","STRING","REQUIRED"), ("crop_id","STRING","REQUIRED"), ("reference_year","INTEGER","NULLABLE"),
            ("season","STRING","REQUIRED"), ("province","STRING","NULLABLE"), ("province_id","STRING","NULLABLE"),
            ("department","STRING","NULLABLE"), ("department_id","STRING","NULLABLE"), ("planted_area_ha","FLOAT","NULLABLE"),
            ("harvested_area_ha","FLOAT","NULLABLE"), ("production_t","FLOAT","NULLABLE"), ("yield_kg_ha","FLOAT","NULLABLE"),
            ("evidence_class","STRING","REQUIRED"), ("source_url","STRING","NULLABLE"), ("source_hash","STRING","REQUIRED"),
            ("data_coleta","TIMESTAMP","REQUIRED"), ("raw_artifact_ref","STRING","NULLABLE"),
            ("source_updated_at","TIMESTAMP","NULLABLE"),
        )]
        table = self.bq.Table(stage, schema=schema)
        table.expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.client.create_table(table)
        try:
            cfg = self.bq.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(payload, stage, job_config=cfg).result()
            self.client.query(f"""
MERGE `{self.table}` T
USING (
 SELECT * EXCEPT(rn) FROM (
   SELECT S.*, ROW_NUMBER() OVER(PARTITION BY snapshot_id, record_id ORDER BY record_id) rn
   FROM `{stage}` S
 ) WHERE rn=1
) S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage, not_found_ok=True)

        cfg = self.bq.QueryJobConfig(query_parameters=[
            self.bq.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)
        ])
        rows = list(self.client.query(
            f"SELECT COUNT(*) n FROM `{self.table}` WHERE snapshot_id=@snapshot_id", job_config=cfg
        ).result())
        persisted = int(rows[0]["n"]) if rows else 0
        if persisted != expected:
            raise RuntimeError(f"Argentina tie-out falhou: esperado={expected} persistido={persisted}")
        return {"status": "loaded_or_existing", "snapshot_id": snapshot_id, "records": persisted, "target": self.table}


class WasdeBigQueryLoader:
    def __init__(self, *, project_id: str, location: str = "southamerica-east1", client: Any | None = None) -> None:
        from google.cloud import bigquery
        self.bq = bigquery
        self.project_id = _safe(project_id, "project_id")
        self.location = location
        self.client = client or bigquery.Client(project=self.project_id, location=location)
        self.table = f"{self.project_id}.global_market.usda_wasde_cells"

    def ensure_objects(self) -> None:
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.global_market` OPTIONS(location='{self.location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.table}` (
 snapshot_id STRING NOT NULL,
 record_id STRING NOT NULL,
 semantic_key STRING NOT NULL,
 semantic_occurrence INT64 NOT NULL,
 cell_index INT64 NOT NULL,
 source_id STRING NOT NULL,
 release_year INT64 NOT NULL,
 release_month INT64 NOT NULL,
 publication_date DATE,
 path STRING NOT NULL,
 attributes_json STRING NOT NULL,
 raw_text STRING,
 numeric_value FLOAT64,
 evidence_class STRING NOT NULL,
 source_url STRING NOT NULL,
 source_hash STRING NOT NULL,
 data_coleta TIMESTAMP NOT NULL,
 raw_artifact_ref STRING
)
PARTITION BY publication_date
CLUSTER BY semantic_key, release_year, release_month, snapshot_id
""").result()

    def load(
        self,
        cells: list[WasdeCell],
        *,
        artifact: WasdeArtifact,
        payload: bytes,
        data_coleta: str,
        publication_date: date | None = None,
        raw_artifact_ref: str | None = None,
    ) -> dict[str, Any]:
        if not cells:
            raise ValueError("WASDE loader recusou lote vazio")
        self.ensure_objects()
        digest = artifact_hash(payload)
        snapshot_id = f"wasde:{artifact.year:04d}-{artifact.month:02d}:{digest[:24]}"
        occurrences: Counter[tuple[str, str]] = Counter()
        rows: list[dict[str, Any]] = []
        for cell in cells:
            key = (cell.path, cell.attributes_json)
            occurrence = occurrences[key]
            occurrences[key] += 1
            semantic_key = _stable_hash([cell.path, cell.attributes_json, str(occurrence)])
            rows.append({
                "snapshot_id": snapshot_id,
                "record_id": _stable_hash([snapshot_id, str(cell.cell_index), semantic_key]),
                "semantic_key": semantic_key,
                "semantic_occurrence": occurrence,
                "cell_index": cell.cell_index,
                "source_id": "usda_wasde",
                "release_year": artifact.year,
                "release_month": artifact.month,
                "publication_date": publication_date.isoformat() if publication_date else None,
                "path": cell.path,
                "attributes_json": cell.attributes_json,
                "raw_text": cell.raw_text or None,
                "numeric_value": cell.numeric_value,
                "evidence_class": "INFORMADO",
                "source_url": artifact.url,
                "source_hash": digest,
                "data_coleta": data_coleta,
                "raw_artifact_ref": raw_artifact_ref,
            })

        stage = f"{self.project_id}.global_market._stg_wasde_{int(datetime.now(timezone.utc).timestamp())}"
        schema = [self.bq.SchemaField(name, typ, mode=mode) for name, typ, mode in (
            ("snapshot_id","STRING","REQUIRED"), ("record_id","STRING","REQUIRED"), ("semantic_key","STRING","REQUIRED"),
            ("semantic_occurrence","INTEGER","REQUIRED"), ("cell_index","INTEGER","REQUIRED"), ("source_id","STRING","REQUIRED"),
            ("release_year","INTEGER","REQUIRED"), ("release_month","INTEGER","REQUIRED"), ("publication_date","DATE","NULLABLE"),
            ("path","STRING","REQUIRED"), ("attributes_json","STRING","REQUIRED"), ("raw_text","STRING","NULLABLE"),
            ("numeric_value","FLOAT","NULLABLE"), ("evidence_class","STRING","REQUIRED"), ("source_url","STRING","REQUIRED"),
            ("source_hash","STRING","REQUIRED"), ("data_coleta","TIMESTAMP","REQUIRED"), ("raw_artifact_ref","STRING","NULLABLE"),
        )]
        table = self.bq.Table(stage, schema=schema)
        table.expires = datetime.now(timezone.utc) + timedelta(hours=2)
        self.client.create_table(table)
        try:
            cfg = self.bq.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE")
            self.client.load_table_from_json(rows, stage, job_config=cfg).result()
            self.client.query(f"""
MERGE `{self.table}` T
USING `{stage}` S
ON T.snapshot_id=S.snapshot_id AND T.record_id=S.record_id
WHEN NOT MATCHED THEN INSERT ROW
""").result()
        finally:
            self.client.delete_table(stage, not_found_ok=True)

        cfg = self.bq.QueryJobConfig(query_parameters=[
            self.bq.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id)
        ])
        count = list(self.client.query(
            f"SELECT COUNT(*) n FROM `{self.table}` WHERE snapshot_id=@snapshot_id", job_config=cfg
        ).result())
        persisted = int(count[0]["n"]) if count else 0
        if persisted != len(rows):
            raise RuntimeError(f"WASDE tie-out falhou: esperado={len(rows)} persistido={persisted}")
        return {"status": "loaded_or_existing", "snapshot_id": snapshot_id, "records": persisted, "target": self.table}
