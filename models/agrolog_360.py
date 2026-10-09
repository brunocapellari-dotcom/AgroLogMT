from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Iterable, Sequence


def _non_negative(value: float, name: str) -> float:
    number = float(value)
    if number < 0:
        raise ValueError(f"{name} não pode ser negativo")
    return number


@dataclass(frozen=True)
class ClimateDay:
    reference_date: date
    precipitation_mm: float | None = None
    tmin_c: float | None = None
    tmax_c: float | None = None


@dataclass(frozen=True)
class FreightMetrics:
    announced_brl_per_t: float
    distance_km: float | None
    brl_per_t_km: float | None
    payload_t: float | None
    announced_brl_per_trip: float | None

    def to_dict(self) -> dict[str, float | None]:
        return asdict(self)


@dataclass(frozen=True)
class StorageBalance:
    production_t: float
    carry_in_t: float
    static_capacity_t: float
    supply_to_capacity_ratio: float | None
    capacity_gap_t: float
    status: str

    def to_dict(self) -> dict[str, float | str | None]:
        return asdict(self)


@dataclass(frozen=True)
class ExportParity:
    port_fob_usd_per_t: float
    fx_brl_per_usd: float
    gross_port_brl_per_t: float
    deductions_brl_per_t: float
    farmgate_parity_brl_per_t: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class PortPressure:
    anchorage_vessels: int
    berth_vessels: int
    programmed_mass_t: float
    observed_throughput_t_day: float
    queue_to_berth_ratio: float | None
    programmed_days_of_throughput: float | None
    pressure_index: float | None

    def to_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def rolling_precipitation(
    rows: Iterable[ClimateDay],
    *,
    windows: Sequence[int] = (7, 15, 30, 60, 90),
    as_of: date | None = None,
) -> dict[int, float | None]:
    """Return trailing precipitation totals using only observations <= as_of.

    Missing days do not become zero. A window returns None unless at least one
    precipitation observation exists inside that trailing period.
    """
    normalized = sorted(rows, key=lambda row: row.reference_date)
    if not normalized:
        return {int(window): None for window in windows}
    end = as_of or normalized[-1].reference_date
    out: dict[int, float | None] = {}
    for raw_window in windows:
        window = int(raw_window)
        if window <= 0:
            raise ValueError("janela deve ser positiva")
        start_ordinal = end.toordinal() - window + 1
        values = [
            float(row.precipitation_mm)
            for row in normalized
            if start_ordinal <= row.reference_date.toordinal() <= end.toordinal()
            and row.precipitation_mm is not None
        ]
        out[window] = round(sum(values), 3) if values else None
    return out


def storage_balance(
    *,
    production_t: float,
    static_capacity_t: float,
    carry_in_t: float = 0.0,
) -> StorageBalance:
    production = _non_negative(production_t, "production_t")
    capacity = _non_negative(static_capacity_t, "static_capacity_t")
    carry = _non_negative(carry_in_t, "carry_in_t")
    supply = production + carry
    gap = capacity - supply
    ratio = None if capacity == 0 else supply / capacity
    if capacity == 0 and supply > 0:
        status = "NO_CAPACITY"
    elif gap < 0:
        status = "DEFICIT"
    elif ratio is not None and ratio >= 0.85:
        status = "TIGHT"
    else:
        status = "SURPLUS"
    return StorageBalance(
        production_t=production,
        carry_in_t=carry,
        static_capacity_t=capacity,
        supply_to_capacity_ratio=round(ratio, 6) if ratio is not None else None,
        capacity_gap_t=round(gap, 3),
        status=status,
    )


def normalize_freight(
    *,
    value_brl: float,
    unit: str,
    distance_km: float | None = None,
    payload_t: float | None = None,
) -> FreightMetrics:
    value = _non_negative(value_brl, "value_brl")
    normalized_unit = str(unit).strip().upper().replace(" ", "")
    distance = None if distance_km is None else _non_negative(distance_km, "distance_km")
    payload = None if payload_t is None else _non_negative(payload_t, "payload_t")

    if normalized_unit in {"BRL/T", "R$/T", "BRL_PER_T"}:
        per_t = value
        per_trip = per_t * payload if payload is not None else None
    elif normalized_unit in {"BRL/TRIP", "R$/VIAGEM", "BRL_PER_TRIP"}:
        if not payload or payload <= 0:
            raise ValueError("payload_t é obrigatório para frete por viagem")
        per_trip = value
        per_t = value / payload
    else:
        raise ValueError(f"unidade de frete não homologada: {unit!r}")

    per_t_km = None
    if distance is not None:
        if distance <= 0:
            raise ValueError("distance_km deve ser > 0 para calcular R$/t.km")
        per_t_km = per_t / distance

    return FreightMetrics(
        announced_brl_per_t=round(per_t, 6),
        distance_km=distance,
        brl_per_t_km=round(per_t_km, 8) if per_t_km is not None else None,
        payload_t=payload,
        announced_brl_per_trip=round(per_trip, 6) if per_trip is not None else None,
    )


def export_parity(
    *,
    port_fob_usd_per_t: float,
    fx_brl_per_usd: float,
    inland_freight_brl_per_t: float,
    port_cost_brl_per_t: float = 0.0,
    taxes_and_fees_brl_per_t: float = 0.0,
) -> ExportParity:
    fob = _non_negative(port_fob_usd_per_t, "port_fob_usd_per_t")
    fx = _non_negative(fx_brl_per_usd, "fx_brl_per_usd")
    freight = _non_negative(inland_freight_brl_per_t, "inland_freight_brl_per_t")
    port = _non_negative(port_cost_brl_per_t, "port_cost_brl_per_t")
    fees = _non_negative(taxes_and_fees_brl_per_t, "taxes_and_fees_brl_per_t")
    gross = fob * fx
    deductions = freight + port + fees
    return ExportParity(
        port_fob_usd_per_t=round(fob, 6),
        fx_brl_per_usd=round(fx, 6),
        gross_port_brl_per_t=round(gross, 6),
        deductions_brl_per_t=round(deductions, 6),
        farmgate_parity_brl_per_t=round(gross - deductions, 6),
    )


def fertilizer_exchange_ratio(*, fertilizer_brl_per_t: float, grain_brl_per_t: float) -> float:
    fertilizer = _non_negative(fertilizer_brl_per_t, "fertilizer_brl_per_t")
    grain = _non_negative(grain_brl_per_t, "grain_brl_per_t")
    if grain <= 0:
        raise ValueError("grain_brl_per_t deve ser > 0")
    return round(fertilizer / grain, 6)


def port_pressure(
    *,
    anchorage_vessels: int,
    berth_vessels: int,
    programmed_mass_t: float,
    observed_throughput_t_day: float,
) -> PortPressure:
    anchorage = int(anchorage_vessels)
    berth = int(berth_vessels)
    if anchorage < 0 or berth < 0:
        raise ValueError("contagens de navios não podem ser negativas")
    programmed = _non_negative(programmed_mass_t, "programmed_mass_t")
    throughput = _non_negative(observed_throughput_t_day, "observed_throughput_t_day")

    queue_ratio = None if berth == 0 else anchorage / berth
    days = None if throughput == 0 else programmed / throughput

    # Descriptive index only: 0-100, not a forecast or service-level claim.
    index = None
    if queue_ratio is not None or days is not None:
        queue_component = min(1.0, (queue_ratio or 0.0) / 4.0)
        mass_component = min(1.0, (days or 0.0) / 7.0)
        index = 100.0 * (0.5 * queue_component + 0.5 * mass_component)

    return PortPressure(
        anchorage_vessels=anchorage,
        berth_vessels=berth,
        programmed_mass_t=round(programmed, 3),
        observed_throughput_t_day=round(throughput, 3),
        queue_to_berth_ratio=round(queue_ratio, 6) if queue_ratio is not None else None,
        programmed_days_of_throughput=round(days, 6) if days is not None else None,
        pressure_index=round(index, 3) if index is not None else None,
    )


def competence_from_reference(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        parsed = date.fromisoformat(str(value)[:10])
    return f"{parsed.year:04d}-{parsed.month:02d}"
