from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


ZONE_PRIORITY = {"UNKNOWN": 0, "SEA": 1, "APPROACH": 2, "ANCHORAGE": 3, "BERTH": 4}


@dataclass(frozen=True)
class PortZone:
    zone_id: str
    port_id: str
    zone: str
    polygon: tuple[tuple[float, float], ...]  # (lat, lon)
    geofence_version: str
    terminal_id: str | None = None
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.zone.upper() not in ZONE_PRIORITY:
            raise ValueError(f"zone invalida: {self.zone}")
        if len(self.polygon) < 3:
            raise ValueError("polygon precisa de ao menos 3 vertices")


def point_in_polygon(latitude: float, longitude: float, polygon: Sequence[tuple[float, float]]) -> bool:
    """Ray-casting for small port polygons away from the antimeridian."""
    x, y = float(longitude), float(latitude)
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def classify_position(
    latitude: float,
    longitude: float,
    zones: Iterable[PortZone],
    *,
    preferred_port_id: str | None = None,
) -> dict[str, str | None]:
    hits: list[PortZone] = []
    for zone in zones:
        if preferred_port_id and zone.port_id != preferred_port_id:
            continue
        if point_in_polygon(latitude, longitude, zone.polygon):
            hits.append(zone)
    if not hits:
        return {
            "zone": "SEA",
            "port_id": preferred_port_id,
            "terminal_id": None,
            "zone_id": None,
            "geofence_version": None,
            "source_id": None,
        }
    best = max(hits, key=lambda z: (ZONE_PRIORITY[z.zone.upper()], z.terminal_id is not None))
    return {
        "zone": best.zone.upper(),
        "port_id": best.port_id,
        "terminal_id": best.terminal_id,
        "zone_id": best.zone_id,
        "geofence_version": best.geofence_version,
        "source_id": best.source_id,
    }
