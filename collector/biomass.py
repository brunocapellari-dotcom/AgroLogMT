from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any


OBSERVED = "OBSERVADO"
ESTIMATED = "ESTIMADO"
INFERRED = "INFERIDO"


@dataclass(frozen=True)
class BiomassObservation:
    source_id: str
    geo_id: str
    biomass_type: str
    metric_id: str
    value: float
    unit: str
    data_referencia: str
    data_publicacao: str | None
    data_coleta: str
    competencia: str
    evidence_class: str
    observation_semantics: str
    source_quality: str
    quality_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["quality_flags"] = list(self.quality_flags)
        return row


def _date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _ts(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def classify_biomass_evidence(*, metric_id: str, derivation: str) -> tuple[str, str]:
    metric = str(metric_id).strip().lower()
    method = str(derivation).strip().lower()

    if method in {"agricultural_volume_x_residue_coefficient", "coefficient_estimate"}:
        return ESTIMATED, "ESTIMATIVA_POR_COEFICIENTE"
    if metric in {"electric_generation_mwh", "generation_mwh"} and method in {"metered", "ons_observed"}:
        return OBSERVED, "SINAL_DE_OPERACAO_GERACAO"
    if metric in {"forest_movement_t", "forest_movement_m3"} and method in {"sisflora_guide", "dof_guide"}:
        return OBSERVED, "MOVIMENTACAO_FLORESTAL_OBSERVADA"
    if metric in {"industrial_consumption_t", "industrial_consumption_m3"}:
        if method not in {"declared", "licensed_report", "company_report", "authorized_data"}:
            raise ValueError("consumo industrial exige declaração/licenciamento/relatório/dado autorizado")
        return OBSERVED, "CONSUMO_INDUSTRIAL_DECLARADO"
    return OBSERVED if method in {"official_observation", "declared"} else INFERRED, "OUTRA_EVIDENCIA"


def normalize_biomass_observation(
    *,
    source_id: str,
    geo_id: str,
    biomass_type: str,
    metric_id: str,
    value: float,
    unit: str,
    reference_date: date | datetime | str,
    collected_at: datetime | str,
    derivation: str,
    published_at: datetime | str | None = None,
    source_quality: str = "primary_high",
) -> BiomassObservation:
    number = float(value)
    if number < 0:
        raise ValueError("value não pode ser negativo")
    reference = _date(reference_date)
    evidence_class, semantics = classify_biomass_evidence(metric_id=metric_id, derivation=derivation)
    flags: list[str] = []
    if evidence_class != OBSERVED:
        flags.append("not_direct_observation")

    collected = _ts(collected_at)
    if collected is None:
        raise ValueError("collected_at obrigatório")

    return BiomassObservation(
        source_id=str(source_id).strip(),
        geo_id=str(geo_id).strip(),
        biomass_type=str(biomass_type).strip(),
        metric_id=str(metric_id).strip(),
        value=number,
        unit=str(unit).strip(),
        data_referencia=reference.isoformat(),
        data_publicacao=_ts(published_at),
        data_coleta=collected,
        competencia=f"{reference.year:04d}-{reference.month:02d}",
        evidence_class=evidence_class,
        observation_semantics=semantics,
        source_quality=str(source_quality).strip(),
        quality_flags=tuple(flags),
    )
