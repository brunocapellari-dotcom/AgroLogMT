from __future__ import annotations

from dataclasses import asdict, dataclass
from math import floor
from typing import Any, Iterable


@dataclass(frozen=True)
class ClimateGridPoint:
    grid_id: str
    latitude: float
    longitude: float
    spacing_deg: float
    boundary_source: str = "IBGE_UF_51"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _polygons(geometry: dict[str, Any]) -> Iterable[list[list[list[float]]]]:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        yield coordinates
    elif kind == "MultiPolygon":
        yield from coordinates
    else:
        raise ValueError("geometry deve ser Polygon ou MultiPolygon")


def geometry_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for polygon in _polygons(geometry):
        for ring in polygon:
            for coord in ring:
                if len(coord) >= 2:
                    xs.append(float(coord[0]))
                    ys.append(float(coord[1]))
    if not xs:
        raise ValueError("geometria sem coordenadas")
    return min(xs), min(ys), max(xs), max(ys)


def _point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if (yi > y) != (yj > y):
            cross_x = (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi
            if x < cross_x:
                inside = not inside
        j = i
    return inside


def point_in_geometry(longitude: float, latitude: float, geometry: dict[str, Any]) -> bool:
    for polygon in _polygons(geometry):
        if not polygon or not _point_in_ring(longitude, latitude, polygon[0]):
            continue
        if any(_point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def generate_grid(geometry: dict[str, Any], *, spacing_deg: float = 0.5) -> list[ClimateGridPoint]:
    if not 0.05 <= spacing_deg <= 2.0:
        raise ValueError("spacing_deg fora do intervalo permitido")
    min_x, min_y, max_x, max_y = geometry_bounds(geometry)
    start_x = floor(min_x / spacing_deg) * spacing_deg + spacing_deg / 2
    start_y = floor(min_y / spacing_deg) * spacing_deg + spacing_deg / 2
    points: list[ClimateGridPoint] = []
    y = start_y
    while y <= max_y + 1e-9:
        x = start_x
        while x <= max_x + 1e-9:
            lon = round(x, 6)
            lat = round(y, 6)
            if point_in_geometry(lon, lat, geometry):
                grid_id = f"mtg_{lat:+09.4f}_{lon:+010.4f}".replace("+", "p").replace("-", "m")
                points.append(ClimateGridPoint(grid_id, lat, lon, spacing_deg))
            x += spacing_deg
        y += spacing_deg
    points.sort(key=lambda row: (row.latitude, row.longitude))
    if not points:
        raise ValueError("grade climática vazia")
    return points
