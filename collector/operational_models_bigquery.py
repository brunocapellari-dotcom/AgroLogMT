from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable


class OperationalModelsBigQueryStore:
    """Canonical BigQuery persistence for M01-M08 observations, scores and lineage."""

    def __init__(self, *, project_id: str | None = None, dataset_id: str = "agrolog_models",
                 location: str | None = None, client: Any | None = None) -> None:
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AGROLOG_GCP_PROJECT")
        if not self.project_id:
            raise ValueError("Defina GOOGLE_CLOUD_PROJECT ou AGROLOG_GCP_PROJECT")
        self.dataset_id = dataset_id
        self.location = location or os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
        from google.cloud import bigquery
        self.bq = bigquery
        self.client = client or bigquery.Client(project=self.project_id, location=self.location)
        self.lineage_table = f"{self.project_id}.{self.dataset_id}.data_lineage"
        self.observations_table = f"{self.project_id}.{self.dataset_id}.model_observations"
        self.scores_table = f"{self.project_id}.{self.dataset_id}.model_scores"

    def ensure_objects(self) -> None:
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{self.location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.lineage_table}` (
 load_id STRING NOT NULL, model_id STRING NOT NULL, source_id STRING NOT NULL,
 source_file STRING, source_hash STRING, source_version STRING,
 collected_at TIMESTAMP NOT NULL, reference_start DATE, reference_end DATE,
 row_count INT64, transformation STRING, transformation_version STRING,
 status STRING NOT NULL, metadata_json STRING, inserted_at TIMESTAMP NOT NULL
) PARTITION BY DATE(inserted_at) CLUSTER BY model_id, source_id, status
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.observations_table}` (
 record_id STRING NOT NULL, load_id STRING NOT NULL, model_id STRING NOT NULL,
 data_referencia DATE NOT NULL, entity_type STRING NOT NULL, entity_id STRING NOT NULL,
 metric_name STRING NOT NULL, value FLOAT64, unit STRING, evidence_class STRING NOT NULL,
 source_id STRING NOT NULL, dimensions_json STRING, collected_at TIMESTAMP NOT NULL
) PARTITION BY data_referencia CLUSTER BY model_id, metric_name, entity_id
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.scores_table}` (
 score_id STRING NOT NULL, load_id STRING NOT NULL, model_id STRING NOT NULL,
 data_referencia DATE NOT NULL, entity_id STRING NOT NULL, model_version STRING NOT NULL,
 score FLOAT64, risk_class STRING, confidence FLOAT64, gate STRING NOT NULL,
 components_json STRING, metadata_json STRING, calculated_at TIMESTAMP NOT NULL
) PARTITION BY data_referencia CLUSTER BY model_id, entity_id, model_version
""").result()

    @staticmethod
    def stable_id(*parts: Any) -> str:
        payload = "|".join("" if p is None else str(p) for p in parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_json(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        errors = self.client.insert_rows_json(table, rows)
        if errors:
            raise RuntimeError(f"Falha BigQuery {table}: {errors}")
        return len(rows)

    def write_lineage(self, *, load_id: str, model_id: str, source_id: str,
                      collected_at: str, status: str, source_file: str | None = None,
                      source_hash: str | None = None, source_version: str | None = None,
                      reference_start: str | None = None, reference_end: str | None = None,
                      row_count: int | None = None, transformation: str | None = None,
                      transformation_version: str | None = None,
                      metadata: dict[str, Any] | None = None) -> int:
        self.ensure_objects()
        row = {
            "load_id": load_id, "model_id": model_id, "source_id": source_id,
            "source_file": source_file, "source_hash": source_hash, "source_version": source_version,
            "collected_at": collected_at, "reference_start": reference_start, "reference_end": reference_end,
            "row_count": row_count, "transformation": transformation,
            "transformation_version": transformation_version, "status": status,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
            "inserted_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._load_json(self.lineage_table, [row])

    def load_observations(self, rows: Iterable[dict[str, Any]], *, load_id: str,
                          model_id: str, source_id: str, collected_at: str) -> int:
        self.ensure_objects()
        normalized: list[dict[str, Any]] = []
        for row in rows:
            data_referencia = str(row["data_referencia"])
            entity_type = str(row["entity_type"])
            entity_id = str(row["entity_id"])
            metric_name = str(row["metric_name"])
            record_id = row.get("record_id") or self.stable_id(model_id, data_referencia, entity_type, entity_id, metric_name, row.get("value"))
            normalized.append({
                "record_id": record_id, "load_id": load_id, "model_id": model_id,
                "data_referencia": data_referencia, "entity_type": entity_type, "entity_id": entity_id,
                "metric_name": metric_name, "value": row.get("value"), "unit": row.get("unit"),
                "evidence_class": row.get("evidence_class", "observado"), "source_id": source_id,
                "dimensions_json": json.dumps(row.get("dimensions", {}), ensure_ascii=False, sort_keys=True),
                "collected_at": collected_at,
            })
        return self._load_json(self.observations_table, normalized)

    def load_scores(self, rows: Iterable[dict[str, Any]], *, load_id: str,
                    model_id: str, model_version: str, gate: str) -> int:
        self.ensure_objects()
        now = datetime.now(timezone.utc).isoformat()
        normalized = []
        for row in rows:
            score_id = row.get("score_id") or self.stable_id(model_id, model_version, row["data_referencia"], row["entity_id"])
            normalized.append({
                "score_id": score_id, "load_id": load_id, "model_id": model_id,
                "data_referencia": str(row["data_referencia"]), "entity_id": str(row["entity_id"]),
                "model_version": model_version, "score": row.get("score"), "risk_class": row.get("risk_class"),
                "confidence": row.get("confidence"), "gate": gate,
                "components_json": json.dumps(row.get("components", {}), ensure_ascii=False, sort_keys=True),
                "metadata_json": json.dumps(row.get("metadata", {}), ensure_ascii=False, sort_keys=True),
                "calculated_at": now,
            })
        return self._load_json(self.scores_table, normalized)
