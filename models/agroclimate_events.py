from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AgroClimateEvent:
    event_type: str
    percentile: float
    anomaly_pct: float | None
    evidence_class: str = "DERIVADO_DE_OBSERVADO"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def precipitation_anomaly_pct(observed_mm: float, climatology_mm: float) -> float | None:
    observed = float(observed_mm)
    climatology = float(climatology_mm)
    if observed < 0 or climatology < 0:
        raise ValueError("precipitação não pode ser negativa")
    if climatology == 0:
        return None
    return round(100.0 * (observed - climatology) / climatology, 3)


def classify_precipitation_percentile(
    percentile: float,
    *,
    dry_extreme_max: float = 5.0,
    dry_max: float = 20.0,
    wet_min: float = 80.0,
    wet_extreme_min: float = 95.0,
    anomaly_pct: float | None = None,
) -> AgroClimateEvent:
    p = float(percentile)
    if not 0 <= p <= 100:
        raise ValueError("percentile deve estar entre 0 e 100")
    if not 0 <= dry_extreme_max <= dry_max < wet_min <= wet_extreme_min <= 100:
        raise ValueError("limiares percentílicos inválidos")

    if p <= dry_extreme_max:
        event = "DRY_EXTREME"
    elif p <= dry_max:
        event = "DRY"
    elif p >= wet_extreme_min:
        event = "WET_EXTREME"
    elif p >= wet_min:
        event = "WET"
    else:
        event = "NORMAL_RANGE"
    return AgroClimateEvent(event, p, anomaly_pct)
