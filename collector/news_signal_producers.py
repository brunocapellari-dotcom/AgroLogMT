from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date
from typing import Any

from collector.bcb_ptax import PtaxQuote, dollar_day_url
from collector.conab_safra import ConabSafraRecord
from collector.news_signals import NewsSignal
from collector.port_lifecycle import PortCallObservation, promote_state


def _canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _score(value: float) -> float:
    score = float(value)
    if not 0 <= score <= 100:
        raise ValueError("materiality_score deve estar entre 0 e 100")
    return score


def _closing_kind(value: str | None) -> bool:
    return (value or "").strip().lower() in {"fechamento", "closing", "final"}


def ptax_closing_change_signal(
    current: PtaxQuote,
    previous: PtaxQuote,
    *,
    data_coleta: str,
    materiality_score: float,
) -> NewsSignal:
    """Create a signal only from two explicit official PTAX closings.

    The function never promotes intraday quotes or a previous-day value as the
    current closing. Materiality is supplied by an external policy rather than
    inferred here so the data adapter cannot silently change editorial thresholds.
    """
    if not _closing_kind(current.bulletin_type) or not _closing_kind(previous.bulletin_type):
        raise ValueError("PTAX change exige dois boletins oficiais de Fechamento")
    current_date = date.fromisoformat(current.reference_date)
    previous_date = date.fromisoformat(previous.reference_date)
    if current_date <= previous_date:
        raise ValueError("PTAX current deve ser posterior ao previous")

    absolute = current.sell - previous.sell
    pct = (absolute / previous.sell * 100.0) if previous.sell else None
    current_payload = asdict(current)
    evidence_id = f"bcb_ptax:USD:{current.reference_date}:{current.quote_time}:closing"
    return NewsSignal(
        source_id="bcb_ptax_olinda",
        dataset_id="bcb_ptax_usd_daily",
        variable="usd_brl_ptax_sell",
        scope="BR",
        signal_class="RELEASE_CHANGE",
        evidence_class="observado",
        data_referencia=current.reference_date,
        data_coleta=data_coleta,
        rule_version="ptax_closing_change.v1",
        baseline_version="previous_official_closing.v1",
        evidence_genealogy_key=f"ptax:USD:{current.reference_date}",
        transformation_type="DIFFERENCE",
        materiality_score=_score(materiality_score),
        competencia=current.reference_date,
        source_url=dollar_day_url(current_date),
        source_observation_id=evidence_id,
        upstream_evidence_ids=(evidence_id,),
        upstream_dataset_ids=("bcb_ptax_usd_daily",),
        transformation_chain=("official_closing_filter", "difference_vs_previous_official_closing"),
        primary_observation_hash=_canonical_hash(current_payload),
        unit="BRL/USD",
        value=current.sell,
        previous_value=previous.sell,
        summary=f"PTAX venda fechou em {current.sell:.4f} BRL/USD; fechamento anterior {previous.sell:.4f}.",
        extra={
            "buy": current.buy,
            "previous_buy": previous.buy,
            "absolute_change": absolute,
            "pct_change": pct,
            "bulletin_type": current.bulletin_type,
            "previous_reference_date": previous.reference_date,
        },
    )


def conab_production_revision_signal(
    current: ConabSafraRecord,
    previous: ConabSafraRecord,
    *,
    current_release_id: str,
    previous_release_id: str,
    data_referencia: str,
    data_publicacao: str,
    data_coleta: str,
    source_url: str,
    materiality_score: float,
) -> NewsSignal:
    """Represent a revision between two distinct CONAB publications.

    `previous` and `current` must refer to the same crop/season/geography. The
    function refuses comparisons between the workbook's previous-season and
    current-season rows; caller must provide two distinct publication IDs.
    """
    if not current_release_id.strip() or not previous_release_id.strip() or current_release_id == previous_release_id:
        raise ValueError("CONAB revision exige dois release_ids distintos")
    natural_current = (current.geo_level, current.geo_id, current.product_id, current.safra)
    natural_previous = (previous.geo_level, previous.geo_id, previous.product_id, previous.safra)
    if natural_current != natural_previous:
        raise ValueError("registros CONAB não representam a mesma safra/geografia/produto")
    blocking = "area_yield_production_identity_material"
    if blocking in current.quality_flags or blocking in previous.quality_flags:
        raise ValueError("revisão CONAB bloqueada por inconsistência material área×produtividade×produção")

    absolute = current.producao_mil_t - previous.producao_mil_t
    pct = (absolute / previous.producao_mil_t * 100.0) if previous.producao_mil_t else None
    evidence_id = f"conab_safra:{current_release_id}:{current.geo_id}:{current.product_id}:{current.safra}"
    return NewsSignal(
        source_id="conab_safra_graos_xlsx",
        dataset_id="conab_safra_graos",
        variable="producao_mil_t",
        scope=f"{current.geo_level}:{current.geo_id}:{current.product_id}:{current.safra}",
        signal_class="RELEASE_CHANGE",
        evidence_class="estimado",
        data_referencia=data_referencia,
        data_publicacao=data_publicacao,
        data_coleta=data_coleta,
        rule_version="conab_production_revision.v1",
        baseline_version="previous_official_release.v1",
        evidence_genealogy_key=f"conab:{current.geo_id}:{current.product_id}:{current.safra}:{current_release_id}",
        transformation_type="DIFFERENCE",
        materiality_score=_score(materiality_score),
        competencia=current.safra,
        source_url=source_url,
        source_observation_id=evidence_id,
        upstream_evidence_ids=(evidence_id,),
        upstream_dataset_ids=("conab_safra_graos",),
        transformation_chain=("official_release_pair", "same_natural_key", "production_difference"),
        primary_observation_hash=_canonical_hash(current.to_dict()),
        unit="mil_t",
        value=current.producao_mil_t,
        previous_value=previous.producao_mil_t,
        summary=(
            f"CONAB revisou {current.product_id} {current.geo_id} {current.safra} para "
            f"{current.producao_mil_t:.1f} mil t; publicação anterior {previous.producao_mil_t:.1f} mil t."
        ),
        extra={
            "current_release_id": current_release_id,
            "previous_release_id": previous_release_id,
            "absolute_change_mil_t": absolute,
            "pct_change": pct,
            "area_mil_ha": current.area_mil_ha,
            "produtividade_kg_ha": current.produtividade_kg_ha,
            "previous_area_mil_ha": previous.area_mil_ha,
            "previous_produtividade_kg_ha": previous.produtividade_kg_ha,
            "quality_score": current.quality_score,
        },
    )


def hydrology_delta_signal(
    delta: dict[str, Any],
    *,
    data_coleta: str,
    source_id: str,
    dataset_id: str,
    source_url: str,
    materiality_score: float,
    signal_class: str = "MOMENTUM",
) -> NewsSignal:
    """Create a hydrology signal only from a non-interpolated observed delta."""
    if delta.get("status") != "OBSERVED_DELTA" or delta.get("interpolated") is not False:
        raise ValueError("sinal hidrológico exige OBSERVED_DELTA sem interpolação")
    field = str(delta.get("field") or "")
    if field not in {"river_level_cm", "discharge_m3_s"}:
        raise ValueError("campo hidrológico inválido")
    if signal_class not in {"MOMENTUM", "LEVEL_BREAK", "EXTREME", "REVERSAL", "REGIME_SHIFT"}:
        raise ValueError("signal_class hidrológico inválido")
    station = str(delta.get("station_code") or "").strip()
    if not station:
        raise ValueError("station_code obrigatório")
    end_at = str(delta.get("end_at") or "")
    start_at = str(delta.get("start_at") or "")
    evidence_id = f"hydro:{dataset_id}:{station}:{field}:{end_at}"
    unit = "cm" if field == "river_level_cm" else "m3/s"
    return NewsSignal(
        source_id=source_id,
        dataset_id=dataset_id,
        variable=field,
        scope=f"station:{station}",
        signal_class=signal_class,  # type: ignore[arg-type]
        evidence_class="observado",
        data_referencia=end_at,
        data_coleta=data_coleta,
        rule_version="hydrology_observed_delta.v1",
        baseline_version=f"observed_{int(delta['days'])}d_endpoint.v1",
        evidence_genealogy_key=f"hydro:{dataset_id}:{station}:{field}:{end_at}:{int(delta['days'])}d",
        transformation_type="DIFFERENCE",
        materiality_score=_score(materiality_score),
        source_url=source_url,
        source_observation_id=evidence_id,
        upstream_evidence_ids=(evidence_id,),
        upstream_dataset_ids=(dataset_id,),
        transformation_chain=("real_observation_endpoints", "no_interpolation", f"delta_{int(delta['days'])}d"),
        primary_observation_hash=_canonical_hash(delta),
        unit=unit,
        value=delta.get("end_value"),
        previous_value=delta.get("start_value"),
        summary=f"{field} na estação {station}: variação observada de {delta.get('delta')} {unit} em {int(delta['days'])} dia(s).",
        extra={
            "days": int(delta["days"]),
            "delta": delta.get("delta"),
            "start_at": start_at,
            "end_at": end_at,
            "interpolated": False,
        },
    )


def port_state_transition_signal(
    previous: PortCallObservation,
    current: PortCallObservation,
    *,
    data_coleta: str,
    materiality_score: float,
) -> NewsSignal:
    """Create a signal only when an official port-call lifecycle state advances."""
    promoted = promote_state(previous, current)
    if previous.state == promoted.state:
        raise ValueError("replay sem mudança de estado não gera NEWS_SIGNAL")
    evidence_id = f"port_call:{promoted.event_key}:{promoted.observed_at}"
    return NewsSignal(
        source_id=f"port_authority:{promoted.port_system.lower()}",
        dataset_id="official_port_call_lifecycle",
        variable="port_call_state",
        scope=promoted.port_system,
        signal_class="RELEASE_CHANGE",
        evidence_class="observado",
        data_referencia=promoted.data_referencia,
        data_coleta=data_coleta,
        rule_version="port_call_transition.v1",
        baseline_version="previous_official_state.v1",
        evidence_genealogy_key=f"port:{promoted.event_key}:{promoted.state}",
        transformation_type="OTHER",
        materiality_score=_score(materiality_score),
        source_url=promoted.source_url,
        source_observation_id=evidence_id,
        upstream_evidence_ids=(evidence_id,),
        upstream_dataset_ids=("official_port_call_lifecycle",),
        transformation_chain=("official_port_observation", "monotonic_state_transition"),
        primary_observation_hash=_canonical_hash(promoted.to_dict()),
        value=promoted.state,
        previous_value=previous.state,
        summary=f"{promoted.port_system}: {promoted.event_key} avançou de {previous.state} para {promoted.state}.",
        extra={
            "event_key": promoted.event_key,
            "ship_name": promoted.ship_name,
            "imo": promoted.imo,
            "duv": promoted.duv,
            "terminal": promoted.terminal,
            "cargo": promoted.cargo,
            "quantity_programmed_t": promoted.quantity_programmed_t,
            "quantity_realized_t": promoted.quantity_realized_t,
            "berth_at": promoted.berth_at,
            "unberth_at": promoted.unberth_at,
        },
    )
