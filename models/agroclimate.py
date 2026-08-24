from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class DailyWaterBalance:
    date: str
    precipitation_mm: float
    eto_mm: float
    storage_mm: float
    deficit_mm: float
    surplus_mm: float
    methodology_id: str = "ALMT_WB_BUCKET_V1"

    def to_dict(self):
        return asdict(self)


def growing_degree_days(tmin_c: float, tmax_c: float, *, base_c: float = 10.0, cap_c: float | None = None) -> float:
    lo = float(tmin_c)
    hi = float(tmax_c)
    if cap_c is not None:
        lo = min(lo, cap_c)
        hi = min(hi, cap_c)
    return max(0.0, ((lo + hi) / 2.0) - base_c)


def bucket_water_balance(
    rows: Iterable[tuple[str, float, float]],
    *,
    storage_capacity_mm: float,
    initial_storage_mm: float | None = None,
) -> list[DailyWaterBalance]:
    """Simple auditable climatic water balance.

    Inputs are (date, precipitation_mm, eto_mm). This is not a crop model and does not
    replace calibrated soil/crop rooting dynamics. It is a baseline/feature generator.
    """
    if storage_capacity_mm <= 0:
        raise ValueError("storage_capacity_mm must be positive")
    storage = storage_capacity_mm if initial_storage_mm is None else float(initial_storage_mm)
    storage = min(max(storage, 0.0), storage_capacity_mm)
    out: list[DailyWaterBalance] = []
    for date, precipitation, eto in rows:
        p = max(0.0, float(precipitation))
        e = max(0.0, float(eto))
        available = storage + p
        actual_et = min(e, available)
        remaining = available - actual_et
        surplus = max(0.0, remaining - storage_capacity_mm)
        storage = min(storage_capacity_mm, remaining)
        deficit = max(0.0, e - actual_et)
        out.append(DailyWaterBalance(
            date=str(date), precipitation_mm=p, eto_mm=e,
            storage_mm=storage, deficit_mm=deficit, surplus_mm=surplus,
        ))
    return out
