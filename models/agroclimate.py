from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date as Date
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


@dataclass(frozen=True)
class WaterBalanceSummary:
    days: int
    precipitation_mm: float
    eto_mm: float
    deficit_mm: float
    surplus_mm: float
    deficit_days: int
    surplus_days: int
    ending_storage_mm: float
    methodology_id: str = "ALMT_WB_BUCKET_SUMMARY_V1"

    def to_dict(self):
        return asdict(self)


def growing_degree_days(tmin_c: float, tmax_c: float, *, base_c: float = 10.0, cap_c: float | None = None) -> float:
    lo = float(tmin_c)
    hi = float(tmax_c)
    if hi < lo:
        raise ValueError("tmax_c deve ser >= tmin_c")
    if cap_c is not None:
        lo = min(lo, cap_c)
        hi = min(hi, cap_c)
    return max(0.0, ((lo + hi) / 2.0) - base_c)


def extraterrestrial_radiation_mj_m2_day(*, latitude_deg: float, day_of_year: int) -> float:
    """FAO-56 extraterrestrial radiation Ra, MJ m-2 day-1."""
    if not -90.0 <= latitude_deg <= 90.0:
        raise ValueError("latitude_deg fora de [-90,90]")
    if not 1 <= day_of_year <= 366:
        raise ValueError("day_of_year fora de [1,366]")
    phi = math.radians(latitude_deg)
    dr = 1.0 + 0.033 * math.cos((2.0 * math.pi / 365.0) * day_of_year)
    solar_declination = 0.409 * math.sin((2.0 * math.pi / 365.0) * day_of_year - 1.39)
    argument = -math.tan(phi) * math.tan(solar_declination)
    argument = min(1.0, max(-1.0, argument))
    sunset_hour_angle = math.acos(argument)
    gsc = 0.0820
    ra = (
        (24.0 * 60.0 / math.pi)
        * gsc
        * dr
        * (
            sunset_hour_angle * math.sin(phi) * math.sin(solar_declination)
            + math.cos(phi) * math.cos(solar_declination) * math.sin(sunset_hour_angle)
        )
    )
    return max(0.0, ra)


def hargreaves_samani_eto_mm(
    *,
    tmin_c: float,
    tmax_c: float,
    tmean_c: float | None,
    latitude_deg: float,
    day_of_year: int,
) -> float:
    """ET0 Hargreaves-Samani como baseline auditável quando FAO-56 PM não está disponível.

    Ra é calculada pela geometria solar FAO-56 e convertida de MJ m-2 d-1 para
    equivalente de evaporação (0,408 mm por MJ m-2). Esta função é baseline e não
    substitui Penman-Monteith quando radiação, vento, umidade e pressão confiáveis
    estiverem disponíveis.
    """
    tmin = float(tmin_c)
    tmax = float(tmax_c)
    if tmax < tmin:
        raise ValueError("tmax_c deve ser >= tmin_c")
    tmean = (tmin + tmax) / 2.0 if tmean_c is None else float(tmean_c)
    ra_mj = extraterrestrial_radiation_mj_m2_day(latitude_deg=latitude_deg, day_of_year=day_of_year)
    ra_mm = 0.408 * ra_mj
    thermal_range = max(0.0, tmax - tmin)
    return max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(thermal_range) * ra_mm)


def hargreaves_samani_eto_for_date(
    date: str,
    *,
    tmin_c: float,
    tmax_c: float,
    tmean_c: float | None,
    latitude_deg: float,
) -> float:
    parsed = Date.fromisoformat(date)
    return hargreaves_samani_eto_mm(
        tmin_c=tmin_c,
        tmax_c=tmax_c,
        tmean_c=tmean_c,
        latitude_deg=latitude_deg,
        day_of_year=parsed.timetuple().tm_yday,
    )


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


def summarize_water_balance(rows: Iterable[DailyWaterBalance], *, epsilon_mm: float = 1e-9) -> WaterBalanceSummary:
    values = list(rows)
    if not values:
        raise ValueError("water balance vazio")
    return WaterBalanceSummary(
        days=len(values),
        precipitation_mm=sum(row.precipitation_mm for row in values),
        eto_mm=sum(row.eto_mm for row in values),
        deficit_mm=sum(row.deficit_mm for row in values),
        surplus_mm=sum(row.surplus_mm for row in values),
        deficit_days=sum(row.deficit_mm > epsilon_mm for row in values),
        surplus_days=sum(row.surplus_mm > epsilon_mm for row in values),
        ending_storage_mm=values[-1].storage_mm,
    )
