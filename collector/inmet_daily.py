from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .agroclimate import AgroClimateObservation, normalize_daily_observation


DEFAULT_FIELD_MAP = {
    "date": ("data", "data_referencia", "date"),
    "precipitation_mm": ("precipitacao_mm", "precipitacao", "chuva_mm", "precipitation"),
    "tmin_c": ("tmin_c", "temperatura_minima", "temp_min"),
    "tmax_c": ("tmax_c", "temperatura_maxima", "temp_max"),
}


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    return float(text)


def normalize_inmet_daily_row(
    row: Mapping[str, Any],
    *,
    geo_id: str,
    collected_at: datetime | str | None = None,
    published_at: datetime | str | None = None,
    field_map: Mapping[str, tuple[str, ...]] | None = None,
) -> AgroClimateObservation:
    """Normalize an already-acquired INMET daily record.

    Network acquisition stays separate until the exact official endpoint/license is
    homologated. This function never guesses a date or substitutes missing weather
    variables with zero.
    """
    fields = dict(DEFAULT_FIELD_MAP)
    if field_map:
        fields.update(field_map)
    reference = _first(row, fields["date"])
    if reference is None:
        raise ValueError("INMET: data de referência ausente")
    collected = collected_at or datetime.now(timezone.utc)
    return normalize_daily_observation(
        source_id="inmet_weather",
        geo_id=geo_id,
        reference_date=str(reference)[:10],
        collected_at=collected,
        published_at=published_at,
        precipitation_mm=_float(_first(row, fields["precipitation_mm"])),
        tmin_c=_float(_first(row, fields["tmin_c"])),
        tmax_c=_float(_first(row, fields["tmax_c"])),
        evidence_class="OBSERVADO",
    )
