from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Iterable, Sequence


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def percentile_rank(history: Sequence[float], value: float) -> float:
    clean = sorted(float(x) for x in history if x is not None and math.isfinite(float(x)))
    if not clean:
        raise ValueError("history vazio")
    below = sum(x < value for x in clean)
    equal = sum(x == value for x in clean)
    return 100.0 * (below + 0.5 * equal) / len(clean)


def zscore(history: Sequence[float], value: float) -> float:
    clean = [float(x) for x in history if x is not None and math.isfinite(float(x))]
    if len(clean) < 2:
        return 0.0
    sd = pstdev(clean)
    return 0.0 if sd == 0 else (float(value) - mean(clean)) / sd


def hhi(shares: Iterable[float]) -> float:
    vals = [float(s) for s in shares if s is not None and s >= 0]
    total = sum(vals)
    if total <= 0:
        return 0.0
    return sum((s / total) ** 2 for s in vals)


def regime_shift(*, previous_hhi: float, current_hhi: float, previous_top_share: float,
                 current_top_share: float, leader_changed: bool,
                 hhi_threshold: float = 0.08, share_threshold_pp: float = 10.0) -> bool:
    return bool(
        abs(current_hhi - previous_hhi) > hhi_threshold
        or abs(current_top_share - previous_top_share) > share_threshold_pp
        or leader_changed
    )


def freight_pressure_label(route_percentiles: Sequence[float]) -> dict[str, float | str]:
    vals = [clamp(x) for x in route_percentiles if x is not None]
    if not vals:
        return {"median_percentile": 0.0, "share_ge_p85": 0.0, "share_ge_p90": 0.0, "label": "UNKNOWN"}
    med = sorted(vals)[len(vals) // 2]
    p85 = sum(v >= 85 for v in vals) / len(vals)
    p90 = sum(v >= 90 for v in vals) / len(vals)
    if med >= 85 or p90 >= 0.35:
        label = "HIGH"
    elif med >= 70 or p85 >= 0.30:
        label = "ELEVATED"
    elif med >= 55 or p85 >= 0.15:
        label = "ATTENTION"
    else:
        label = "NORMAL"
    return {"median_percentile": med, "share_ge_p85": p85, "share_ge_p90": p90, "label": label}


def ramp_adjusted_activity_score(*, yoy_growth_pct: float, utilization_pct: float,
                                 capacity_step_pct: float = 0.0,
                                 months_since_step: int | None = None) -> float:
    growth_score = clamp(50.0 + yoy_growth_pct * 2.0)
    utilization_score = clamp(utilization_pct)
    in_ramp = capacity_step_pct > 3.0 and months_since_step is not None and 0 <= months_since_step <= 3
    growth_weight = 0.70 if in_ramp else 0.45
    utilization_weight = 1.0 - growth_weight
    return clamp(growth_weight * growth_score + utilization_weight * utilization_score)


def absorption_scenarios(capacity_t_day: float, operating_days: int = 30,
                         utilization_low: float = 0.65, utilization_base: float = 0.80,
                         utilization_high: float = 0.92) -> dict[str, float]:
    base = float(capacity_t_day) * int(operating_days)
    return {
        "low_t": base * utilization_low,
        "base_t": base * utilization_base,
        "high_t": base * utilization_high,
    }


def hydro_percentile_risk(stage_percentile: float) -> float:
    """Hydrological low-stage risk: lower seasonal percentile => higher risk."""
    p = clamp(stage_percentile)
    if p >= 25:
        return 0.0
    if p >= 10:
        return 25.0
    if p >= 5:
        return 50.0
    if p >= 1:
        return 75.0
    return 100.0


def m04_score(h: float, t: float, p: float, f: float, o: float) -> float:
    return clamp(0.30 * h + 0.15 * t + 0.15 * p + 0.20 * f + 0.20 * o)


def m04_class(score: float) -> str:
    s = clamp(score)
    if s < 25:
        return "NORMAL"
    if s < 45:
        return "ATTENTION"
    if s < 65:
        return "ELEVATED"
    if s < 80:
        return "HIGH"
    return "CRITICAL"


@dataclass(frozen=True)
class ModelGate:
    model_id: str
    concept: bool = False
    data: bool = False
    backtest: bool = False
    operational: bool = False
    predictive: bool = False

    @property
    def highest_gate(self) -> str:
        if self.predictive:
            return "PREDICTIVE"
        if self.operational:
            return "OPERATIONAL"
        if self.backtest:
            return "BACKTEST"
        if self.data:
            return "DATA"
        if self.concept:
            return "CONCEPT"
        return "NOT_STARTED"
