from __future__ import annotations

import atexit
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from collector.ais_stream_client import run_forever
from collector.shipping_bigquery import ShippingBigQueryStore
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


class AisBatchSink:
    def __init__(self, *, store: ShippingBigQueryStore, zones: list[PortZone], batch_size: int = 250) -> None:
        self.store = store
        self.zones = zones
        self.batch_size = max(1, int(batch_size))
        self.buffer: list[dict[str, Any]] = []
        atexit.register(self.flush)

    def _normalize(self, row: dict[str, Any]) -> dict[str, Any]:
        lat, lon = row.get("latitude"), row.get("longitude")
        geofence = {
            "zone": "SEA", "port_id": None, "terminal_id": None,
            "zone_id": None, "geofence_version": None, "source_id": None,
        }
        if lat is not None and lon is not None and self.zones:
            geofence = classify_position(float(lat), float(lon), self.zones)
        raw_message = row.get("_raw_message")
        return {
            "observation_id": _observation_id(row),
            "mmsi": row.get("mmsi"),
            "imo": row.get("imo"),
            "vessel_name": row.get("vessel_name"),
            "observed_at": row["observed_at"],
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
        }

    def __call__(self, row: dict[str, Any]) -> None:
        self.buffer.append(self._normalize(row))
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self) -> int:
        if not self.buffer:
            return 0
        rows = self.buffer
        self.buffer = []
        return self.store.load_ais(rows)


def main() -> int:
    api_key = os.environ.get("AISSTREAM_API_KEY")
    if not api_key:
        raise RuntimeError("AISSTREAM_API_KEY obrigatoria")
    bounding_boxes = _json_env("AIS_BOUNDING_BOXES_JSON", required=True)
    mmsi_filter = _json_env("AIS_MMSI_FILTER_JSON", default=None)
    zones = _zones_from_env()
    batch_size = int(os.environ.get("AIS_BATCH_SIZE", "250"))
    max_records_raw = os.environ.get("AIS_MAX_RECORDS")
    max_records = int(max_records_raw) if max_records_raw else None
    capture_seconds = float(os.environ.get("AIS_CAPTURE_SECONDS", "3000"))

    store = ShippingBigQueryStore()
    sink = AisBatchSink(store=store, zones=zones, batch_size=batch_size)
    delivered = run_forever(
        api_key=api_key,
        bounding_boxes=bounding_boxes,
        mmsi_filter=mmsi_filter,
        on_record=sink,
        stop_after_records=max_records,
        stop_after_seconds=capture_seconds,
    )
    sink.flush()
    print(json.dumps({"status": "ok", "records": delivered, "zones": len(zones), "capture_seconds": capture_seconds}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
