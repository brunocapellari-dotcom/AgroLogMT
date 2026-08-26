from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_subscription(api_key: str, bounding_boxes: list[list[list[float]]], mmsi_filter: list[str] | None = None) -> dict[str, Any]:
    if not api_key:
        raise ValueError("AIS API key obrigatoria")
    if not bounding_boxes:
        raise ValueError("ao menos um bounding box obrigatorio")
    payload: dict[str, Any] = {
        "APIKey": api_key,
        "BoundingBoxes": bounding_boxes,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    if mmsi_filter:
        payload["FiltersShipMMSI"] = [str(x) for x in mmsi_filter]
    return payload


def _first(mapping: dict[str, Any], *names: str) -> Any:
    lower = {str(k).lower(): v for k, v in mapping.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_now(value: Any = None) -> str:
    if value:
        text = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


def parse_aisstream_message(payload: dict[str, Any], *, received_at: str | None = None) -> dict[str, Any] | None:
    """Normalize AISStream-style websocket payloads.

    This parser intentionally does not infer port/terminal/geofence. That enrichment
    belongs to the port-geofence layer so raw AIS remains source-faithful.
    """
    if not isinstance(payload, dict):
        return None
    meta = payload.get("MetaData") or payload.get("metadata") or {}
    message = payload.get("Message") or payload.get("message") or {}
    msg_type = payload.get("MessageType") or payload.get("messageType") or ""
    if not isinstance(message, dict):
        return None

    body = message.get(msg_type) if msg_type in message else None
    if not isinstance(body, dict):
        body = next((v for v in message.values() if isinstance(v, dict)), message)

    mmsi = _first(meta, "MMSI", "Mmsi") or _first(body, "UserID", "MMSI", "Mmsi")
    if not mmsi:
        return None

    normalized = {
        "message_type": str(msg_type or "UNKNOWN"),
        "mmsi": str(mmsi),
        "imo": str(_first(meta, "IMO", "Imo") or _first(body, "ImoNumber", "IMO") or "") or None,
        "vessel_name": _first(meta, "ShipName", "Name") or _first(body, "Name", "ShipName"),
        "observed_at": _iso_now(_first(meta, "time_utc", "TimeUtc", "Timestamp") or received_at),
        "latitude": _float(_first(meta, "latitude", "Latitude") or _first(body, "Latitude")),
        "longitude": _float(_first(meta, "longitude", "Longitude") or _first(body, "Longitude")),
        "sog_kn": _float(_first(body, "Sog", "SpeedOverGround")),
        "cog_deg": _float(_first(body, "Cog", "CourseOverGround")),
        "navigation_status": _first(body, "NavigationalStatus", "NavigationStatus"),
        "destination": _first(body, "Destination"),
        "source_id": "aisstream",
    }
    return normalized
