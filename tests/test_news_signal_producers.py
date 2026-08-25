from __future__ import annotations

from collector.bcb_ptax import PtaxQuote
from collector.conab_safra import ConabSafraRecord
from collector.news_signal_producers import (
    conab_production_revision_signal,
    hydrology_delta_signal,
    port_state_transition_signal,
    ptax_closing_change_signal,
)
from collector.port_lifecycle import PortCallObservation


def _conab(production: float, *, geo_id: str = "MT", product_id: str = "soja", safra: str = "25/26") -> ConabSafraRecord:
    return ConabSafraRecord(
        source_id="conab_safra_graos_xlsx",
        geo_level="uf",
        geo_id=geo_id,
        produto_origem="SOJA",
        product_id=product_id,
        safra=safra,
        vintage_position="current",
        area_mil_ha=13000.0,
        produtividade_kg_ha=3600.0,
        producao_mil_t=production,
        area_var_pct=None,
        produtividade_var_pct=None,
        producao_var_pct=None,
        identity_error_mil_t=0.0,
        identity_error_pct=0.0,
        quality_score=1.0,
        quality_flags=(),
        source_sheet="MT",
        source_row=10,
    )


def _port(state: str, *, berth_at: str | None = None, unberth_at: str | None = None) -> PortCallObservation:
    return PortCallObservation(
        port_system="SANTOS",
        source_url="https://www.portodesantos.com.br/official",
        observed_at="2026-08-25T12:00:00+00:00",
        data_referencia="2026-08-25",
        ship_name="TEST SHIP",
        imo="1234567",
        duv="DUV-1",
        terminal="T1",
        cargo="SOJA",
        state=state,
        quantity_programmed_t=50000.0,
        quantity_realized_t=None,
        berth_at=berth_at,
        unberth_at=unberth_at,
    )


def test_ptax_signal_requires_explicit_closings() -> None:
    current = PtaxQuote("2026-08-25", "2026-08-25T13:10:00-03:00", 5.20, 5.21, "Fechamento")
    previous = PtaxQuote("2026-08-24", "2026-08-24T13:10:00-03:00", 5.10, 5.11, "Fechamento")
    signal = ptax_closing_change_signal(current, previous, data_coleta="2026-08-25T13:15:00-03:00", materiality_score=60)
    assert signal.evidence_class == "observado"
    assert signal.value == 5.21
    assert signal.previous_value == 5.11
    assert signal.extra["pct_change"] is not None


def test_ptax_intraday_is_blocked() -> None:
    current = PtaxQuote("2026-08-25", "2026-08-25T11:00:00-03:00", 5.20, 5.21, "Intermediário")
    previous = PtaxQuote("2026-08-24", "2026-08-24T13:10:00-03:00", 5.10, 5.11, "Fechamento")
    try:
        ptax_closing_change_signal(current, previous, data_coleta="2026-08-25T11:05:00-03:00", materiality_score=50)
    except ValueError as exc:
        assert "Fechamento" in str(exc)
    else:
        raise AssertionError("PTAX intraday não pode gerar closing signal")


def test_conab_revision_uses_two_distinct_publications() -> None:
    previous = _conab(46500.0)
    current = _conab(47000.0)
    signal = conab_production_revision_signal(
        current,
        previous,
        current_release_id="conab-2026-08",
        previous_release_id="conab-2026-07",
        data_referencia="2026-08-13",
        data_publicacao="2026-08-13T09:00:00-03:00",
        data_coleta="2026-08-25T11:00:00-04:00",
        source_url="https://www.gov.br/conab/official",
        materiality_score=70,
    )
    assert signal.signal_class == "RELEASE_CHANGE"
    assert signal.evidence_class == "estimado"
    assert signal.extra["absolute_change_mil_t"] == 500.0


def test_conab_same_release_is_blocked() -> None:
    current = _conab(47000.0)
    previous = _conab(46500.0)
    try:
        conab_production_revision_signal(
            current,
            previous,
            current_release_id="same",
            previous_release_id="same",
            data_referencia="2026-08-13",
            data_publicacao="2026-08-13T09:00:00-03:00",
            data_coleta="2026-08-25T11:00:00-04:00",
            source_url="https://www.gov.br/conab/official",
            materiality_score=70,
        )
    except ValueError as exc:
        assert "release_ids distintos" in str(exc)
    else:
        raise AssertionError("mesma publicação não pode ser tratada como revisão")


def test_hydrology_signal_requires_real_endpoints() -> None:
    delta = {
        "station_code": "15400000",
        "field": "river_level_cm",
        "days": 1,
        "status": "OBSERVED_DELTA",
        "start_at": "2026-08-24T12:00:00+00:00",
        "end_at": "2026-08-25T12:00:00+00:00",
        "start_value": 500.0,
        "end_value": 510.0,
        "delta": 10.0,
        "interpolated": False,
    }
    signal = hydrology_delta_signal(
        delta,
        data_coleta="2026-08-25T12:05:00+00:00",
        source_id="ana_hidroweb",
        dataset_id="hidro.telemetria",
        source_url="https://www.snirh.gov.br/official",
        materiality_score=65,
    )
    assert signal.transformation_type == "DIFFERENCE"
    assert signal.extra["interpolated"] is False
    assert signal.value == 510.0


def test_hydrology_gap_is_blocked() -> None:
    delta = {"station_code": "15400000", "field": "river_level_cm", "days": 1, "status": "DATA_GAP", "delta": None, "interpolated": False}
    try:
        hydrology_delta_signal(
            delta,
            data_coleta="2026-08-25T12:05:00+00:00",
            source_id="ana_hidroweb",
            dataset_id="hidro.telemetria",
            source_url="https://www.snirh.gov.br/official",
            materiality_score=65,
        )
    except ValueError as exc:
        assert "OBSERVED_DELTA" in str(exc)
    else:
        raise AssertionError("DATA_GAP não pode virar sinal")


def test_port_transition_signal_requires_state_advance() -> None:
    previous = _port("PROGRAMADO")
    current = _port("ATRACADO", berth_at="2026-08-25T11:30:00+00:00")
    signal = port_state_transition_signal(previous, current, data_coleta="2026-08-25T12:05:00+00:00", materiality_score=55)
    assert signal.value == "ATRACADO"
    assert signal.previous_value == "PROGRAMADO"
    assert signal.extra["quantity_realized_t"] is None


def test_port_replay_without_state_change_is_not_a_signal() -> None:
    previous = _port("PROGRAMADO")
    current = _port("PROGRAMADO")
    try:
        port_state_transition_signal(previous, current, data_coleta="2026-08-25T12:05:00+00:00", materiality_score=55)
    except ValueError as exc:
        assert "replay" in str(exc)
    else:
        raise AssertionError("replay sem mudança não deve gerar sinal")
