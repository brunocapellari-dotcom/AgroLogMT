from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable


class ShippingBigQueryStore:
    """BigQuery persistence for M01-S line-up, AIS, port operations and reconciliation."""

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
        prefix = f"{self.project_id}.{self.dataset_id}"
        self.lineup = f"{prefix}.shipping_lineup_calls"
        self.ais = f"{prefix}.shipping_ais_positions"
        self.operations = f"{prefix}.shipping_port_operations"
        self.reconciliation = f"{prefix}.shipping_reconciliation"

    def ensure_objects(self) -> None:
        self.client.query(
            f"CREATE SCHEMA IF NOT EXISTS `{self.project_id}.{self.dataset_id}` OPTIONS(location='{self.location}')"
        ).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.lineup}` (
 call_id STRING NOT NULL, snapshot_id STRING NOT NULL, port_id STRING NOT NULL,
 terminal_id STRING, vessel_name STRING NOT NULL, imo STRING, mmsi STRING,
 eta TIMESTAMP NOT NULL, product STRING, planned_volume_t FLOAT64,
 lineup_status STRING NOT NULL, source_id STRING NOT NULL,
 collected_at TIMESTAMP NOT NULL, source_hash STRING, raw_artifact_ref STRING
) PARTITION BY DATE(eta) CLUSTER BY port_id, terminal_id, imo, mmsi
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.ais}` (
 observation_id STRING NOT NULL, mmsi STRING, imo STRING, vessel_name STRING,
 observed_at TIMESTAMP NOT NULL, latitude FLOAT64, longitude FLOAT64,
 sog_kn FLOAT64, cog_deg FLOAT64, navigation_status STRING, destination STRING,
 port_id STRING, terminal_id STRING, zone STRING NOT NULL,
 source_id STRING NOT NULL, collected_at TIMESTAMP NOT NULL,
 raw_artifact_ref STRING, raw_message_json STRING
) PARTITION BY DATE(observed_at) CLUSTER BY mmsi, imo, port_id, zone
""").result()
        self.client.query(f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS raw_message_json STRING").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.operations}` (
 operation_id STRING NOT NULL, call_id STRING NOT NULL, port_id STRING NOT NULL,
 actual_arrival_at TIMESTAMP, berth_at TIMESTAMP, unberth_at TIMESTAMP,
 completed_at TIMESTAMP, actual_volume_t FLOAT64, operation_status STRING,
 source_id STRING NOT NULL, collected_at TIMESTAMP NOT NULL,
 raw_artifact_ref STRING
) PARTITION BY DATE(COALESCE(completed_at, berth_at, actual_arrival_at, collected_at))
CLUSTER BY port_id, call_id, operation_status
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.reconciliation}` (
 reconciliation_id STRING NOT NULL, call_id STRING NOT NULL,
 calculated_at TIMESTAMP NOT NULL, state STRING NOT NULL,
 evidence_class STRING NOT NULL, match_method STRING NOT NULL,
 match_confidence FLOAT64 NOT NULL, matched_imo STRING, matched_mmsi STRING,
 eta_error_hours FLOAT64, waiting_hours FLOAT64, berth_hours FLOAT64,
 volume_variance_pct FLOAT64, flags_json STRING, metadata_json STRING,
 model_version STRING NOT NULL
) PARTITION BY DATE(calculated_at) CLUSTER BY state, match_method, call_id
""").result()

    @staticmethod
    def stable_id(*parts: Any) -> str:
        payload = "|".join("" if p is None else str(p) for p in parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _insert(self, table: str, rows: list[dict[str, Any]], *, row_ids: list[str] | None = None) -> int:
        if not rows:
            return 0
        errors = self.client.insert_rows_json(table, rows, row_ids=row_ids)
        if errors:
            raise RuntimeError(f"Falha BigQuery {table}: {errors}")
        return len(rows)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def load_lineup(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data = list(rows)
        ids = [self.stable_id(r.get("call_id"), r.get("snapshot_id")) for r in data]
        return self._insert(self.lineup, data, row_ids=ids)

    def load_ais(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data = list(rows)
        ids = [str(r["observation_id"]) for r in data]
        return self._insert(self.ais, data, row_ids=ids)

    def load_operations(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data = list(rows)
        ids = [str(r["operation_id"]) for r in data]
        return self._insert(self.operations, data, row_ids=ids)

    def load_reconciliation(self, rows: Iterable[dict[str, Any]], *, model_version: str = "M01-S-v0.1") -> int:
        self.ensure_objects()
        calculated_at = self._now()
        normalized: list[dict[str, Any]] = []
        for row in rows:
            normalized.append({
                "reconciliation_id": row["reconciliation_id"],
                "call_id": row["call_id"],
                "calculated_at": row.get("calculated_at", calculated_at),
                "state": row["state"],
                "evidence_class": row["evidence_class"],
                "match_method": row["match_method"],
                "match_confidence": row["match_confidence"],
                "matched_imo": row.get("matched_imo"),
                "matched_mmsi": row.get("matched_mmsi"),
                "eta_error_hours": row.get("eta_error_hours"),
                "waiting_hours": row.get("waiting_hours"),
                "berth_hours": row.get("berth_hours"),
                "volume_variance_pct": row.get("volume_variance_pct"),
                "flags_json": json.dumps(row.get("flags", []), ensure_ascii=False, sort_keys=True),
                "metadata_json": json.dumps(row.get("metadata", {}), ensure_ascii=False, sort_keys=True),
                "model_version": model_version,
            })
        ids = [str(r["reconciliation_id"]) for r in normalized]
        return self._insert(self.reconciliation, normalized, row_ids=ids)
