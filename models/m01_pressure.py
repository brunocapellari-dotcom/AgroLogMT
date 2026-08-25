from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping

COMPONENTS = ("A", "C", "S", "I", "E", "H", "T", "P")


@dataclass(frozen=True)
class PressureComponent:
    component: str
    score: float | None
    evidence_status: str
    evidence_id: str | None = None
    note: str = ""

    def __post_init__(self):
        if self.component not in COMPONENTS:
            raise ValueError(f"componente M01 inválido: {self.component}")
        if self.score is not None and not 0 <= float(self.score) <= 100:
            raise ValueError("score fora de [0,100]")


@dataclass(frozen=True)
class M01Output:
    corridor: str
    as_of: str
    pressure_vector: dict[str, float | None]
    observed_component_count: int
    missing_components: list[str]
    dominant_pressure: str | None
    pressure_max: float | None
    status: str
    confidence: str
    weighted_score: None = None

    def to_dict(self):
        return asdict(self)


def synthesize_m01(*, corridor: str, as_of: str, components: list[PressureComponent], min_components: int = 4) -> M01Output:
    by_key: Mapping[str, PressureComponent] = {item.component: item for item in components}
    vector = {key: (float(by_key[key].score) if key in by_key and by_key[key].score is not None else None) for key in COMPONENTS}
    available = {k:v for k,v in vector.items() if v is not None}
    missing = [k for k,v in vector.items() if v is None]
    if not available:
        return M01Output(corridor,as_of,vector,0,missing,None,None,"DATA_GAP","LOW")
    dominant=max(available,key=available.get)
    pressure_max=available[dominant]
    if len(available) < min_components:
        status="DATA_GATED"
        confidence="LOW"
    else:
        status="OPERATIONAL_VECTOR"
        confidence="MEDIUM" if len(available)<len(COMPONENTS) else "HIGH"
    # v0.1 intentionally emits no weighted score before validation/backtest.
    return M01Output(corridor,as_of,vector,len(available),missing,dominant,pressure_max,status,confidence)
