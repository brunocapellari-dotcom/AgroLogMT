from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Iterable, Any


VALID_ROUTE_TYPES = {"EXPORT", "DOMESTIC", "IMPORT", "TRANSFER", "UNKNOWN"}
VALID_MODES = {"ROAD", "RAIL", "WATERWAY", "MULTIMODAL"}


@dataclass(frozen=True)
class CorridorObservation:
    corridor_id: str
    origin_geo_id: str
    destination_geo_id: str
    route_type: str
    mode: str
    product_id: str | None = None
    volume_t: float | None = None
    freight_brl_per_t: float | None = None
    freight_brl_per_t_km: float | None = None

    def __post_init__(self) -> None:
        if self.route_type not in VALID_ROUTE_TYPES:
            raise ValueError(f"route_type inválido: {self.route_type}")
        if self.mode not in VALID_MODES:
            raise ValueError(f"mode inválido: {self.mode}")
        if not self.corridor_id or not self.origin_geo_id or not self.destination_geo_id:
            raise ValueError("corridor_id/origem/destino são obrigatórios")
        for name, value in (
            ("volume_t", self.volume_t),
            ("freight_brl_per_t", self.freight_brl_per_t),
            ("freight_brl_per_t_km", self.freight_brl_per_t_km),
        ):
            if value is not None and float(value) < 0:
                raise ValueError(f"{name} não pode ser negativo")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def aggregate_corridors(rows: Iterable[CorridorObservation]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str | None], list[CorridorObservation]] = {}
    for row in rows:
        key = (
            row.corridor_id,
            row.origin_geo_id,
            row.destination_geo_id,
            row.route_type,
            row.product_id,
        )
        grouped.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        corridor_id, origin, destination, route_type, product = key
        volumes = [float(row.volume_t) for row in items if row.volume_t is not None]
        freights = [float(row.freight_brl_per_t) for row in items if row.freight_brl_per_t is not None]
        tkm = [float(row.freight_brl_per_t_km) for row in items if row.freight_brl_per_t_km is not None]
        modes = sorted({row.mode for row in items})
        out.append({
            "corridor_id": corridor_id,
            "origin_geo_id": origin,
            "destination_geo_id": destination,
            "route_type": route_type,
            "product_id": product,
            "modes": modes,
            "observations": len(items),
            "volume_t_sum": round(sum(volumes), 3) if volumes else None,
            "freight_brl_per_t_p50": round(median(freights), 6) if freights else None,
            "freight_brl_per_t_km_p50": round(median(tkm), 8) if tkm else None,
        })
    return out


def multimodal_cost_brl_per_t(*legs_brl_per_t: float) -> float:
    if not legs_brl_per_t:
        raise ValueError("ao menos uma perna é obrigatória")
    values = [float(value) for value in legs_brl_per_t]
    if any(value < 0 for value in values):
        raise ValueError("custos não podem ser negativos")
    return round(sum(values), 6)
