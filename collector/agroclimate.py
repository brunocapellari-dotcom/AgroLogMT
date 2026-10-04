from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any


def _date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class AgroClimateObservation:
    source_id: str
    geo_id: str
    data_referencia: str
    data_publicacao: str | None
    data_coleta: str
    competencia: str
    precipitacao_mm: float | None
    tmin_c: float | None
    tmax_c: float | None
    evidence_class: str
    quality_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["quality_flags"] = list(self.quality_flags)
        return row


def normalize_daily_observation(
    *,
    source_id: str,
    geo_id: str,
    reference_date: date | datetime | str,
    collected_at: datetime | str,
    published_at: datetime | str | None = None,
    precipitation_mm: float | None = None,
    tmin_c: float | None = None,
    tmax_c: float | None = None,
    evidence_class: str = "OBSERVADO",
) -> AgroClimateObservation:
    source = str(source_id).strip()
    geo = str(geo_id).strip()
    if not source or not geo:
        raise ValueError("source_id e geo_id são obrigatórios")

    reference = _date(reference_date)
    flags: list[str] = []

    precip = None if precipitation_mm is None else float(precipitation_mm)
    if precip is not None and precip < 0:
        raise ValueError("precipitation_mm não pode ser negativa")

    tmin = None if tmin_c is None else float(tmin_c)
    tmax = None if tmax_c is None else float(tmax_c)
    if tmin is not None and tmax is not None and tmin > tmax:
        flags.append("tmin_gt_tmax")

    if precip is None:
        flags.append("precipitation_missing")
    if tmin is None:
        flags.append("tmin_missing")
    if tmax is None:
        flags.append("tmax_missing")

    collected = _timestamp(collected_at)
    if collected is None:
        raise ValueError("collected_at obrigatório")

    return AgroClimateObservation(
        source_id=source,
        geo_id=geo,
        data_referencia=reference.isoformat(),
        data_publicacao=_timestamp(published_at),
        data_coleta=collected,
        competencia=f"{reference.year:04d}-{reference.month:02d}",
        precipitacao_mm=precip,
        tmin_c=tmin,
        tmax_c=tmax,
        evidence_class=str(evidence_class).strip().upper(),
        quality_flags=tuple(sorted(set(flags))),
    )
