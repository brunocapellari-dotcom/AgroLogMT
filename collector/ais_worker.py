from __future__ import annotations

import atexit
import hashlib
import json
import os
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from collector.ais_stream_client import run_forever
from collector.shipping_bigquery import ShippingBigQueryStore
from models.ais_quality import assess_ais_record
from models.port_geofence import PortZone, classify_position


def _json_env(name: str, *, required: bool = False, default: Any = None) -> Any:
    raw = os.environ.get(name)
    if not raw:
        if required:
            raise RuntimeError(f"{name} obrigatorio")
        return default
    return json.loads(raw)


def _zones_from_env() -> list[PortZone]:
    payload = _json_env("AIS_PORT_ZONES_JSON", default=[])
    zones: list[PortZone] = []
    for row in payload or []:
        zones.append(PortZone(
            zone_id=str(row["zone_id"]),
            port_id=str(row["port_id"]),
            zone=str(row["zone"]),
            polygon=tuple((float(p[0]), float(p[1])) for p in row["polygon"]),
            geofence_version=str(row["geofence_version"]),
            terminal_id=str(row["terminal_id"]) if row.get("terminal_id") else None,
            source_id=str(row["source_id"]) if row.get("source_id") else None,
        ))
    return zones


def _observation_id(row: dict[str, Any]) -> str:
    payload = "|".join([
        str(row.get("mmsi") or ""),
        str(row.get("observed_at") or ""),
        str(row.get("latitude") or ""),
        str(row.get("longitude") or ""),
        str(row.get("message_type") or ""),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _message_family(row: dict[str, Any]) -> str:
    message_type = str(row.get("message_type") or "").strip().upper().replace("_", "")
    return "POSITION" if message_type.endswith("POSITIONREPORT") or message_type == "POSITIONREPORT" else "STATIC"


class AisBatchSink:
    def __init__(
        self,
        *,
        store: ShippingBigQueryStore,
        zones: list[PortZone],
        run_id: str,
        batch_size: int = 250,
        dedup_window_size: int = 100_000,
    ) -> None:
        self.store = store
        self.zones = zones
        self.run_id = run_id
        self.batch_size = max(1, int(batch_size))
        self.dedup_window_size = max(1_000, int(dedup_window_size))
        self.buffer: list[dict[str, Any]] = []
        self._seen_ids: OrderedDict[str, None] = OrderedDict()
        self._last_by_sequence: dict[str, dict[str, Any]] = {}
        self._valid_sequence_count: dict[str, int] = {}
        self.records_received = 0
        self.records_persisted = 0
        self.duplicates_suppressed = 0
        self.quarantined = 0
        self.last_observation_id: str | None = None
        self.last_observed_at: str | None = None
        atexit.register(self.flush)

    def _remember_id(self, observation_id: str) -> bool:
        if observation_id in self._seen_ids:
            self._seen_ids.move_to_end(observation_id)
            return False
        self._seen_ids[observation_id] = None
        while len(self._seen_ids) > self.dedup_window_size:
            self._seen_ids.popitem(last=False)
        return True

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any] | None:
        self.records_received += 1
        observation_id = _observation_id(row)
        if not self._remember_id(observation_id):
            self.duplicates_suppressed += 1
            return None

        mmsi = str(row.get("mmsi") or "")
        family = _message_family(row)
        sequence_key = f"{mmsi}|{family}"
        previous = self._last_by_sequence.get(sequence_key)
        candidate_sequence_count = self._valid_sequence_count.get(sequence_key, 0) + 1
        quality = assess_ais_record(
            row,
            previous=previous,
            same_identity_message_count=candidate_sequence_count,
        )
        if quality.quality_status == "QUARANTINE":
            self.quarantined += 1
        else:
            self._valid_sequence_count[sequence_key] = candidate_sequence_count
            self._last_by_sequence[sequence_key] = {
                "mmsi": row.get("mmsi"),
                "imo": row.get("imo"),
                "observed_at": row.get("observed_at"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "message_type": row.get("message_type"),
            }

        lat, lon = row.get("latitude"), row.get("longitude")
        geofence = {
            "zone": "SEA", "port_id": None, "terminal_id": None,
            "zone_id": None, "geofence_version": None, "source_id": None,
        }
        if (
            family == "POSITION"
            and quality.corroborated
            and quality.quality_status != "QUARANTINE"
            and lat is not None and lon is not None and self.zones
        ):
            geofence = classify_position(float(lat), float(lon), self.zones)

        raw_message = row.get("_raw_message")
        normalized = {
            "observation_id": observation_id,
            "mmsi": row.get("mmsi"),
            "imo": row.get("imo"),
            "vessel_name": row.get("vessel_name"),
            "observed_at": row.get("observed_at"),
            "source_timestamp_raw": row.get("source_timestamp_raw"),
            "received_at": row.get("received_at"),
            "timestamp_basis": row.get("timestamp_basis"),
            "latitude": lat,
            "longitude": lon,
            "sog_kn": row.get("sog_kn"),
            "cog_deg": row.get("cog_deg"),
            "navigation_status": str(row.get("navigation_status")) if row.get("navigation_status") is not None else None,
            "destination": row.get("destination"),
            "port_id": geofence.get("port_id"),
            "terminal_id": geofence.get("terminal_id"),
            "zone": geofence.get("zone") or "SEA",
            "source_id": row.get("source_id", "aisstream"),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "raw_artifact_ref": None,
            "raw_message_json": json.dumps(raw_message, ensure_ascii=False, separators=(",", ":")) if raw_message else None,
            "quality_status": quality.quality_status,
            "quality_flags_json": json.dumps(list(quality.flags), ensure_ascii=False, separators=(",", ":")),
            "corroborated": quality.corroborated,
            "spoofing_suspected": quality.spoofing_suspected,
            "calculated_speed_kn": quality.calculated_speed_kn,
        }
        self.last_observation_id = observation_id
        self.last_observed_at = row.get("observed_at")
        return normalized

    def __call__(self, row: dict[str, Any]) -> None:
        normalized = self._normalize(row)
        if normalized is None:
            return
        self.buffer.append(normalized)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def _write_checkpoint(self) -> None:
        if not self.last_observation_id:
            return
        checkpoint_at = datetime.now(timezone.utc).isoformat()
        self.store.load_stream_checkpoint({
            "checkpoint_id": self.store.stable_id(
                self.run_id, self.last_observation_id, self.records_persisted
            ),
            "run_id": self.run_id,
            "source_id": "aisstream",
            "checkpoint_at": checkpoint_at,
            "last_observed_at": self.last_observed_at,
            "last_observation_id": self.last_observation_id,
            "records_delivered": self.records_received,
            "records_persisted": self.records_persisted,
            "upstream_offset": None,
            "replay_capable": False,
            "details": {
                "checkpoint_semantics": "LOGICAL_ONLY_NO_UPSTREAM_REPLAY",
                "duplicates_suppressed": self.duplicates_suppressed,
                "quarantined": self.quarantined,
            },
        })

    def flush(self) -> int:
        if not self.buffer:
            return 0
        rows = self.buffer
        self.buffer = []
        inserted = self.store.load_ais(rows)
        self.records_persisted += inserted
        self._write_checkpoint()
        return inserted


def _capture_event(
    store: ShippingBigQueryStore,
    *,
    run_id: str,
    event_type: str,
    aoi_count: int,
    capture_seconds: float,
    records: int | None = None,
    error_type: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    event_at = datetime.now(timezone.utc).isoformat()
    store.load_ais_capture_event({
        "event_id": store.stable_id(run_id, event_type),
        "run_id": run_id,
        "event_type": event_type,
        "event_at": event_at,
        "source_id": "aisstream",
        "records": records,
        "aoi_count": aoi_count,
        "capture_seconds_requested": capture_seconds,
        "error_type": error_type,
        "details": details or {},
    })


def main() -> int:
    api_key = os.environ.get("AISSTREAM_API_KEY")
    if not api_key:
        raise RuntimeError("AISSTREAM_API_KEY obrigatoria")
    bounding_boxes = _json_env("AIS_BOUNDING_BOXES_JSON", required=True)
    mmsi_filter = _json_env("AIS_MMSI_FILTER_JSON", default=None)
    zones = _zones_from_env()
    batch_size = int(os.environ.get("AIS_BATCH_SIZE", "250"))
    dedup_window_size = int(os.environ.get("AIS_DEDUP_WINDOW_SIZE", "100000"))
    heartbeat_seconds = float(os.environ.get("AIS_HEARTBEAT_SECONDS", "30"))
    max_records_raw = os.environ.get("AIS_MAX_RECORDS")
    max_records = int(max_records_raw) if max_records_raw else None
    capture_seconds = float(os.environ.get("AIS_CAPTURE_SECONDS", "3540"))

    store = ShippingBigQueryStore()
    run_id = str(uuid.uuid4())
    sink = AisBatchSink(
        store=store,
        zones=zones,
        run_id=run_id,
        batch_size=batch_size,
        dedup_window_size=dedup_window_size,
    )
    _capture_event(
        store,
        run_id=run_id,
        event_type="START",
        aoi_count=len(bounding_boxes),
        capture_seconds=capture_seconds,
        details={"heartbeat_seconds": heartbeat_seconds},
    )

    try:
        run_forever(
            api_key=api_key,
            bounding_boxes=bounding_boxes,
            on_record=sink,
            mmsi_filter=mmsi_filter,
            max_records=max_records,
            run_seconds=capture_seconds,
            heartbeat_seconds=heartbeat_seconds,
        )
        sink.flush()
    except Exception as exc:
        _capture_event(
            store,
            run_id=run_id,
            event_type="ERROR",
            aoi_count=len(bounding_boxes),
            capture_seconds=capture_seconds,
            records=sink.records_persisted,
            error_type=type(exc).__name__,
            details={
                "records_received": sink.records_received,
                "duplicates_suppressed": sink.duplicates_suppressed,
                "quarantined": sink.quarantined,
            },
        )
        raise

    _capture_event(
        store,
        run_id=run_id,
        event_type="END",
        aoi_count=len(bounding_boxes),
        capture_seconds=capture_seconds,
        records=sink.records_persisted,
        details={
            "records_received": sink.records_received,
            "duplicates_suppressed": sink.duplicates_suppressed,
            "quarantined": sink.quarantined,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
