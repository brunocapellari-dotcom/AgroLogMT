from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable


class ShippingBigQueryStore:
    """Canonical BigQuery persistence for AgroLog Maritime Intelligence.

    Raw/source-faithful observations remain distinct from derived physical events,
    estimates, anomalies and alerts. Derived tables always retain evidence/model
    metadata so no inference can be mistaken for an observed port fact.
    """

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
        self.ais_capture_events = f"{prefix}.shipping_ais_capture_events"
        self.stream_checkpoints = f"{prefix}.shipping_stream_checkpoints"
        self.operations = f"{prefix}.shipping_port_operations"
        self.reconciliation = f"{prefix}.shipping_reconciliation"
        self.port_call_events = f"{prefix}.shipping_port_call_events"
        self.eta_estimates = f"{prefix}.shipping_eta_estimates"
        self.queue_snapshots = f"{prefix}.shipping_queue_snapshots"
        self.source_health = f"{prefix}.shipping_source_health"
        self.anomalies = f"{prefix}.shipping_anomalies"
        self.alert_decisions = f"{prefix}.shipping_alert_decisions"
        self.trade_flow_signals = f"{prefix}.shipping_trade_flow_signals"

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
 observed_at TIMESTAMP NOT NULL, source_timestamp_raw STRING, received_at TIMESTAMP,
 timestamp_basis STRING, latitude FLOAT64, longitude FLOAT64,
 sog_kn FLOAT64, cog_deg FLOAT64, navigation_status STRING, destination STRING,
 port_id STRING, terminal_id STRING, zone STRING NOT NULL,
 source_id STRING NOT NULL, collected_at TIMESTAMP NOT NULL,
 raw_artifact_ref STRING, raw_message_json STRING,
 quality_status STRING, quality_flags_json STRING,
 corroborated BOOL, spoofing_suspected BOOL, calculated_speed_kn FLOAT64
) PARTITION BY DATE(observed_at) CLUSTER BY mmsi, imo, port_id, zone
""").result()
        for statement in (
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS raw_message_json STRING",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS source_timestamp_raw STRING",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS received_at TIMESTAMP",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS timestamp_basis STRING",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS quality_status STRING",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS quality_flags_json STRING",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS corroborated BOOL",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS spoofing_suspected BOOL",
            f"ALTER TABLE `{self.ais}` ADD COLUMN IF NOT EXISTS calculated_speed_kn FLOAT64",
        ):
            self.client.query(statement).result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.ais_capture_events}` (
 event_id STRING NOT NULL, run_id STRING NOT NULL, event_type STRING NOT NULL,
 event_at TIMESTAMP NOT NULL, source_id STRING NOT NULL,
 records INT64, aoi_count INT64, capture_seconds_requested FLOAT64,
 error_type STRING, details_json STRING
) PARTITION BY DATE(event_at) CLUSTER BY event_type, source_id, run_id
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.stream_checkpoints}` (
 checkpoint_id STRING NOT NULL, run_id STRING NOT NULL, source_id STRING NOT NULL,
 checkpoint_at TIMESTAMP NOT NULL, last_observed_at TIMESTAMP,
 last_observation_id STRING, records_delivered INT64, records_persisted INT64,
 upstream_offset STRING, replay_capable BOOL NOT NULL, details_json STRING
) PARTITION BY DATE(checkpoint_at) CLUSTER BY source_id, run_id
""").result()
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
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.port_call_events}` (
 event_id STRING NOT NULL, call_id STRING, mmsi STRING, imo STRING,
 port_id STRING NOT NULL, terminal_id STRING, state STRING NOT NULL,
 occurred_at TIMESTAMP NOT NULL, evidence_class STRING NOT NULL,
 source_kind STRING NOT NULL, confidence FLOAT64 NOT NULL,
 evidence_refs_json STRING, flags_json STRING, model_version STRING NOT NULL
) PARTITION BY DATE(occurred_at) CLUSTER BY port_id, state, imo, mmsi
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.eta_estimates}` (
 estimate_id STRING NOT NULL, mmsi STRING, imo STRING, port_id STRING NOT NULL,
 calculated_at TIMESTAMP NOT NULL, eta TIMESTAMP, eta_low TIMESTAMP, eta_high TIMESTAMP,
 travel_hours FLOAT64, effective_speed_kn FLOAT64, distance_nm FLOAT64,
 distance_method STRING, confidence FLOAT64 NOT NULL, evidence_class STRING NOT NULL,
 status STRING NOT NULL, flags_json STRING, model_version STRING NOT NULL
) PARTITION BY DATE(calculated_at) CLUSTER BY port_id, imo, mmsi, status
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.queue_snapshots}` (
 snapshot_id STRING NOT NULL, port_id STRING NOT NULL, observed_at TIMESTAMP NOT NULL,
 waiting_vessels INT64, approaching_vessels INT64, berthed_vessels INT64,
 p50_wait_hours FLOAT64, p90_wait_hours FLOAT64, historical_percentile FLOAT64,
 zscore FLOAT64, vqi FLOAT64, port_pressure_score FLOAT64,
 status STRING NOT NULL, publication_mode STRING NOT NULL,
 evidence_class STRING NOT NULL, flags_json STRING, model_version STRING NOT NULL
) PARTITION BY DATE(observed_at) CLUSTER BY port_id, status, publication_mode
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.source_health}` (
 health_id STRING NOT NULL, source_id STRING NOT NULL, assessed_at TIMESTAMP NOT NULL,
 status STRING NOT NULL, transport_status STRING NOT NULL, data_status STRING NOT NULL,
 last_success_at TIMESTAMP, last_record_at TIMESTAMP,
 collector_age_minutes FLOAT64, data_age_minutes FLOAT64, flags_json STRING
) PARTITION BY DATE(assessed_at) CLUSTER BY source_id, status
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.anomalies}` (
 anomaly_id STRING NOT NULL, scope STRING NOT NULL, detected_at TIMESTAMP NOT NULL,
 anomaly_type STRING NOT NULL, severity STRING NOT NULL, confidence FLOAT64 NOT NULL,
 evidence_class STRING NOT NULL, summary STRING NOT NULL, evidence_json STRING,
 action STRING, publication_status STRING NOT NULL, model_version STRING NOT NULL
) PARTITION BY DATE(detected_at) CLUSTER BY scope, severity, anomaly_type
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.alert_decisions}` (
 decision_id STRING NOT NULL, alert_key STRING NOT NULL, scope STRING NOT NULL,
 decided_at TIMESTAMP NOT NULL, action STRING NOT NULL, severity STRING NOT NULL,
 reason STRING NOT NULL, anomaly_type STRING NOT NULL, evidence_class STRING NOT NULL,
 publication_status STRING NOT NULL, requires_human_review BOOL NOT NULL
) PARTITION BY DATE(decided_at) CLUSTER BY scope, action, severity
""").result()
        self.client.query(f"""
CREATE TABLE IF NOT EXISTS `{self.trade_flow_signals}` (
 flow_id STRING NOT NULL, port_id STRING NOT NULL, period STRING NOT NULL,
 product STRING NOT NULL, observed_trade_mass_t FLOAT64, programmed_lineup_mass_t FLOAT64,
 programmed_calls INT64, programmed_to_observed_ratio FLOAT64,
 status STRING NOT NULL, evidence_class STRING NOT NULL, flags_json STRING,
 vessel_level_attribution_allowed BOOL NOT NULL, calculated_at TIMESTAMP NOT NULL
) PARTITION BY DATE(calculated_at) CLUSTER BY port_id, product, status
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

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

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

    def load_ais_capture_event(self, row: dict[str, Any]) -> int:
        self.ensure_objects()
        event = {
            "event_id": row["event_id"],
            "run_id": row["run_id"],
            "event_type": row["event_type"],
            "event_at": row.get("event_at", self._now()),
            "source_id": row.get("source_id", "aisstream"),
            "records": row.get("records"),
            "aoi_count": row.get("aoi_count"),
            "capture_seconds_requested": row.get("capture_seconds_requested"),
            "error_type": row.get("error_type"),
            "details_json": self._json(row.get("details", {})),
        }
        return self._insert(self.ais_capture_events, [event], row_ids=[str(event["event_id"])])

    def load_stream_checkpoint(self, row: dict[str, Any]) -> int:
        self.ensure_objects()
        checkpoint = {
            "checkpoint_id": row["checkpoint_id"],
            "run_id": row["run_id"],
            "source_id": row.get("source_id", "aisstream"),
            "checkpoint_at": row.get("checkpoint_at", self._now()),
            "last_observed_at": row.get("last_observed_at"),
            "last_observation_id": row.get("last_observation_id"),
            "records_delivered": row.get("records_delivered"),
            "records_persisted": row.get("records_persisted"),
            "upstream_offset": row.get("upstream_offset"),
            "replay_capable": bool(row.get("replay_capable", False)),
            "details_json": self._json(row.get("details", {})),
        }
        return self._insert(self.stream_checkpoints, [checkpoint], row_ids=[str(checkpoint["checkpoint_id"])])

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
                "flags_json": self._json(row.get("flags", [])),
                "metadata_json": self._json(row.get("metadata", {})),
                "model_version": model_version,
            })
        ids = [str(r["reconciliation_id"]) for r in normalized]
        return self._insert(self.reconciliation, normalized, row_ids=ids)

    def load_port_call_events(self, rows: Iterable[dict[str, Any]], *, model_version: str = "PORT_CALL_V1") -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["event_id"] = item.get("event_id") or self.stable_id(
                item.get("call_id"), item.get("port_id"), item.get("state"), item.get("occurred_at")
            )
            item["evidence_refs_json"] = self._json(item.pop("evidence_refs", []))
            item["flags_json"] = self._json(item.pop("flags", []))
            item["model_version"] = item.get("model_version", model_version)
            data.append(item)
        return self._insert(self.port_call_events, data, row_ids=[str(row["event_id"]) for row in data])

    def load_eta_estimates(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["estimate_id"] = item.get("estimate_id") or self.stable_id(
                item.get("mmsi"), item.get("imo"), item.get("port_id"), item.get("calculated_at"), item.get("model_version")
            )
            item["flags_json"] = self._json(item.pop("flags", []))
            data.append(item)
        return self._insert(self.eta_estimates, data, row_ids=[str(row["estimate_id"]) for row in data])

    def load_queue_snapshots(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["snapshot_id"] = item.get("snapshot_id") or self.stable_id(
                item.get("port_id"), item.get("observed_at"), item.get("model_version")
            )
            item["flags_json"] = self._json(item.pop("flags", []))
            data.append(item)
        return self._insert(self.queue_snapshots, data, row_ids=[str(row["snapshot_id"]) for row in data])

    def load_source_health(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["assessed_at"] = item.get("assessed_at", self._now())
            item["health_id"] = item.get("health_id") or self.stable_id(item.get("source_id"), item["assessed_at"])
            item["flags_json"] = self._json(item.pop("flags", []))
            data.append(item)
        return self._insert(self.source_health, data, row_ids=[str(row["health_id"]) for row in data])

    def load_anomalies(self, rows: Iterable[dict[str, Any]], *, model_version: str = "MARITIME_ANOMALY_V1") -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["detected_at"] = item.get("detected_at", self._now())
            item["model_version"] = item.get("model_version", model_version)
            item["anomaly_id"] = item.get("anomaly_id") or self.stable_id(
                item.get("scope"), item.get("anomaly_type"), item["detected_at"], item.get("model_version")
            )
            item["evidence_json"] = self._json(item.pop("evidence", []))
            data.append(item)
        return self._insert(self.anomalies, data, row_ids=[str(row["anomaly_id"]) for row in data])

    def load_alert_decisions(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["decided_at"] = item.get("decided_at", self._now())
            item["decision_id"] = item.get("decision_id") or self.stable_id(
                item.get("alert_key"), item["decided_at"], item.get("action")
            )
            data.append(item)
        return self._insert(self.alert_decisions, data, row_ids=[str(row["decision_id"]) for row in data])

    def load_trade_flow_signals(self, rows: Iterable[dict[str, Any]]) -> int:
        self.ensure_objects()
        data: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["calculated_at"] = item.get("calculated_at", self._now())
            item["flow_id"] = item.get("flow_id") or self.stable_id(
                item.get("port_id"), item.get("period"), item.get("product"), item["calculated_at"]
            )
            item["flags_json"] = self._json(item.pop("flags", []))
            item["vessel_level_attribution_allowed"] = bool(item.get("vessel_level_attribution_allowed", False))
            data.append(item)
        return self._insert(self.trade_flow_signals, data, row_ids=[str(row["flow_id"]) for row in data])
