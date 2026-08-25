from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from math import floor
from typing import Any, Iterable


@dataclass(frozen=True)
class HydroObservation:
    station_code: str
    observed_at: str
    river_level_cm: float | None = None
    discharge_m3_s: float | None = None
    quality_status: int | None = None
    evidence_class: str = "observado"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NavigationEvent:
    event_id: str
    river_or_corridor: str
    effective_at: str
    event_type: str
    status: str
    source_url: str
    restriction_explicit: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp hidrologico deve conter timezone")
    return parsed.astimezone(timezone.utc)


def _series(rows: Iterable[HydroObservation], station_code: str, field: str) -> list[tuple[datetime, float]]:
    out: list[tuple[datetime, float]] = []
    for row in rows:
        if row.station_code != station_code:
            continue
        value = getattr(row, field)
        if value is None:
            continue
        out.append((_dt(row.observed_at), float(value)))
    out.sort(key=lambda item: item[0])
    return out


def observed_delta(
    rows: Iterable[HydroObservation],
    *,
    station_code: str,
    field: str,
    as_of: datetime,
    days: int,
    tolerance_hours: int = 12,
) -> dict[str, Any]:
    """Compute an observed delta with no interpolation.

    Both endpoints must be real observations within tolerance of the requested times.
    Otherwise the result is DATA_GAP and no numeric delta is emitted.
    """
    if field not in {"river_level_cm", "discharge_m3_s"}:
        raise ValueError("field hidrologico invalido")
    if days <= 0:
        raise ValueError("days deve ser positivo")
    series = _series(rows, station_code, field)
    as_of_utc = as_of.astimezone(timezone.utc)
    target = as_of_utc - timedelta(days=days)
    tolerance = timedelta(hours=tolerance_hours)

    def nearest(moment: datetime) -> tuple[datetime, float] | None:
        candidates = [item for item in series if abs(item[0] - moment) <= tolerance]
        return min(candidates, key=lambda item: abs(item[0] - moment)) if candidates else None

    end = nearest(as_of_utc)
    start = nearest(target)
    if start is None or end is None:
        return {
            "station_code": station_code,
            "field": field,
            "days": days,
            "status": "DATA_GAP",
            "delta": None,
            "interpolated": False,
        }
    return {
        "station_code": station_code,
        "field": field,
        "days": days,
        "status": "OBSERVED_DELTA",
        "start_at": start[0].isoformat(),
        "end_at": end[0].isoformat(),
        "start_value": start[1],
        "end_value": end[1],
        "delta": end[1] - start[1],
        "interpolated": False,
    }


def deltas_1_3_7_15(
    rows: Iterable[HydroObservation], *, station_code: str, field: str, as_of: datetime
) -> list[dict[str, Any]]:
    values = list(rows)
    return [observed_delta(values, station_code=station_code, field=field, as_of=as_of, days=days) for days in (1, 3, 7, 15)]


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if not 0 <= p <= 1:
        raise ValueError("percentil fora de [0,1]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo = floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    weight = pos - lo
    return ordered[lo] * (1 - weight) + ordered[hi] * weight


def day_of_year_climatology(
    rows: Iterable[HydroObservation],
    *,
    station_code: str,
    field: str,
    minimum_years: int = 5,
) -> list[dict[str, Any]]:
    if field not in {"river_level_cm", "discharge_m3_s"}:
        raise ValueError("field hidrologico invalido")
    buckets: dict[int, list[tuple[int, float]]] = {}
    for ts, value in _series(rows, station_code, field):
        buckets.setdefault(ts.timetuple().tm_yday, []).append((ts.year, value))
    out: list[dict[str, Any]] = []
    for doy, items in sorted(buckets.items()):
        years = {year for year, _ in items}
        values = [value for _, value in items]
        status = "READY" if len(years) >= minimum_years else "INSUFFICIENT_HISTORY"
        out.append(
            {
                "station_code": station_code,
                "field": field,
                "day_of_year": doy,
                "years": len(years),
                "observations": len(values),
                "status": status,
                "p01": _percentile(values, 0.01) if status == "READY" else None,
                "p05": _percentile(values, 0.05) if status == "READY" else None,
                "p10": _percentile(values, 0.10) if status == "READY" else None,
                "p25": _percentile(values, 0.25) if status == "READY" else None,
                "p50": _percentile(values, 0.50) if status == "READY" else None,
                "p75": _percentile(values, 0.75) if status == "READY" else None,
                "p90": _percentile(values, 0.90) if status == "READY" else None,
                "p95": _percentile(values, 0.95) if status == "READY" else None,
                "p99": _percentile(values, 0.99) if status == "READY" else None,
            }
        )
    return out


def contextualize_navigation(
    *,
    hydro_summary: dict[str, Any],
    events: Iterable[NavigationEvent],
    river_or_corridor: str,
    as_of: datetime,
    window_days: int = 7,
) -> dict[str, Any]:
    """Attach explicit navigation events without inferring a restriction from river level."""
    start = as_of.astimezone(timezone.utc) - timedelta(days=window_days)
    matched = []
    for event in events:
        when = _dt(event.effective_at)
        if event.river_or_corridor == river_or_corridor and start <= when <= as_of.astimezone(timezone.utc):
            matched.append(event.to_dict())
    return {
        "hydrology": hydro_summary,
        "navigation_events": matched,
        "restriction_observed": any(event["restriction_explicit"] for event in matched),
        "restriction_inferred_from_hydrology": False,
    }
