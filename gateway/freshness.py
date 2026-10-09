from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


COMPONENT_MAX_AGE_MINUTES = {
    "overview": 2880,
    "ptax": 4320,
    "market_reference": 10080,
    "crops_mt": 64800,
    "crops_br": 64800,
    "freight": 2880,
    "weather": 720,
    "weather_3d": 720,
    "weather_7d": 720,
    "weather_15d": 720,
    "hydrology": 2880,
    "crop_progress": 10080,
    "argentina": 43200,
    "usda": 64800,
    "exports": 64800,
}


def _parse_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def component_freshness(
    name: str,
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> tuple[str, str | None, float | None]:
    """Classify one commercial component without importing runtime/GCP clients."""
    if not rows:
        return "FAILED", None, None

    timestamps: list[datetime] = []
    for row in rows:
        for key in ("data_coleta", "collection_time", "latest_source_update", "latest_measurement"):
            parsed = _parse_timestamp(row.get(key))
            if parsed is not None:
                timestamps.append(parsed)
                break

    if not timestamps:
        return "FAILED", None, None

    latest = max(timestamps)
    reference_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_minutes = max(0.0, (reference_now - latest).total_seconds() / 60.0)
    max_age = COMPONENT_MAX_AGE_MINUTES.get(name, 1440)
    return ("FRESH" if age_minutes <= max_age else "STALE"), latest.isoformat(), age_minutes
