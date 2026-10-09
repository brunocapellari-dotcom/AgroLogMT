from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class WeatherForecastObservation:
    source_id: str
    geo_id: str
    model_cycle_at: str
    valid_at: str
    lead_hours: int
    variable: str
    value: float
    unit: str
    data_referencia: str
    data_publicacao: str
    data_coleta: str
    competencia: str
    evidence_class: str = "PROJETADO"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def normalize_cptec_forecast(
    row: Mapping[str, Any],
    *,
    geo_id: str,
    model_cycle_at: datetime | str,
    valid_at: datetime | str,
    variable: str,
    unit: str,
    value_field: str = "value",
    published_at: datetime | str | None = None,
    collected_at: datetime | str | None = None,
) -> WeatherForecastObservation:
    """Normalize a CPTEC/INPE forecast already acquired from an approved product.

    The model/product acquisition contract remains gated until the exact official
    endpoint and usage terms are homologated. Forecasts are permanently PROJETADO.
    """
    cycle = _utc(model_cycle_at)
    valid = _utc(valid_at)
    if valid < cycle:
        raise ValueError("valid_at não pode anteceder model_cycle_at")
    lead = int((valid - cycle).total_seconds() // 3600)
    if value_field not in row or row[value_field] in (None, ""):
        raise ValueError("CPTEC: valor projetado ausente")
    value = float(str(row[value_field]).replace(",", "."))
    published = _utc(published_at or cycle)
    collected = _utc(collected_at or datetime.now(timezone.utc))
    if collected < published:
        raise ValueError("data_coleta não pode anteceder data_publicacao")
    return WeatherForecastObservation(
        source_id="cptec_weather",
        geo_id=str(geo_id).strip(),
        model_cycle_at=cycle.isoformat(),
        valid_at=valid.isoformat(),
        lead_hours=lead,
        variable=str(variable).strip(),
        value=value,
        unit=str(unit).strip(),
        data_referencia=valid.date().isoformat(),
        data_publicacao=published.isoformat(),
        data_coleta=collected.isoformat(),
        competencia=f"{valid.year:04d}-{valid.month:02d}",
    )
