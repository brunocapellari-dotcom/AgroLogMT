from __future__ import annotations

from dataclasses import asdict, dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Any, Iterable


@dataclass(frozen=True)
class BenchmarkResult:
    component: str
    status: str
    duration_ms: float
    metrics: dict[str, Any]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_km = 6371.0088
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 2 * r_km * asin(sqrt(a))


def evaluate_route_case(
    *,
    distance_km: float,
    lower_bound_km: float,
    min_ratio: float,
    max_ratio: float,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    if distance_km <= 0 or lower_bound_km <= 0:
        raise ValueError("distâncias devem ser positivas")
    ratio = distance_km / lower_bound_km
    plausible = min_ratio <= ratio <= max_ratio
    result: dict[str, Any] = {
        "distance_km": round(distance_km, 3),
        "geodesic_lower_bound_km": round(lower_bound_km, 3),
        "road_to_geodesic_ratio": round(ratio, 4),
        "plausible": plausible,
    }
    if duration_seconds is not None:
        if duration_seconds <= 0:
            raise ValueError("duração deve ser positiva")
        result["duration_hours"] = round(duration_seconds / 3600.0, 3)
        result["average_speed_kph"] = round(distance_km / (duration_seconds / 3600.0), 3)
    return result


def summarize(results: Iterable[BenchmarkResult], *, require_no_skips: bool = False) -> dict[str, Any]:
    rows = list(results)
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for row in rows:
        if row.status not in counts:
            raise ValueError(f"status inválido: {row.status}")
        counts[row.status] += 1

    status = "PASS"
    if counts["FAIL"]:
        status = "FAIL"
    elif require_no_skips and counts["SKIP"]:
        status = "FAIL"
    elif counts["SKIP"]:
        status = "PARTIAL"

    return {
        "status": status,
        "counts": counts,
        "total": len(rows),
        "require_no_skips": require_no_skips,
    }
