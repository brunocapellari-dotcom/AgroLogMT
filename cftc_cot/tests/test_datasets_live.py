"""Testes de integração reais contra a API SODA do CFTC Public Reporting (Issue #14).

Fazem chamadas de rede de verdade. Pulam (``pytest.skip``) sempre que o
problema é de conectividade (``SocrataConnectionError``), seguindo a mesma
regra do conector CKAN (Issue #19) e do AgTransport/USDA (Issue #20):
indisponibilidade externa não deve travar o build, mas um erro de contrato
real (payload inesperado, HTTP não-200) é uma regressão e deve falhar o
teste. Diferente de uma versão anterior deste arquivo, isso vale para
*todas* as chamadas de rede do teste, não só uma checagem preliminar —
cada chamada real passa por :func:`_call_or_skip`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import pytest

from cftc_cot.client import SocrataConnectionError, build_client
from cftc_cot.datasets import (
    CADENCE_TOLERANCE_DAYS,
    DATE_FIELD,
    DISAGGREGATED_COMBINED_DATASET_ID,
    KNOWN_CONTRACTS,
)

_client = build_client(timeout=10.0, max_retries=1)


def _call_or_skip(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except SocrataConnectionError as exc:
        pytest.skip(f"CFTC Public Reporting inacessível deste ambiente (rede): {exc}")


def test_dataset_metadata_matches_disaggregated_combined_report():
    metadata = _call_or_skip(lambda: _client.dataset_metadata(DISAGGREGATED_COMBINED_DATASET_ID))

    assert metadata.name == "Disaggregated - Combined"
    assert metadata.category == "Commitments of Traders"
    assert metadata.columns, "dataset não retornou nenhuma coluna"
    field_names = {c.field_name for c in metadata.columns}
    assert DATE_FIELD in field_names
    assert "market_and_exchange_names" in field_names
    assert "cftc_contract_market_code" in field_names


@pytest.mark.parametrize("key", sorted(KNOWN_CONTRACTS))
def test_contract_records_match_registered_name_and_code(key: str):
    config = KNOWN_CONTRACTS[key]

    records = _call_or_skip(
        lambda: _client.query(
            DISAGGREGATED_COMBINED_DATASET_ID,
            select=f"{DATE_FIELD},market_and_exchange_names,cftc_contract_market_code,commodity_name",
            where=f"market_and_exchange_names = '{config.market_and_exchange_names}'",
            order=f"{DATE_FIELD} DESC",
            limit=3,
        )
    )

    assert records, f"{key}: nenhum registro retornado para {config.market_and_exchange_names!r}"
    for record in records:
        assert record["market_and_exchange_names"] == config.market_and_exchange_names
        assert record["cftc_contract_market_code"] == config.cftc_contract_market_code
        assert record["commodity_name"] == config.commodity_name


@pytest.mark.parametrize("key", sorted(KNOWN_CONTRACTS))
def test_cadence_matches_real_weekly_gap_between_recent_reports(key: str):
    """Regressão de cadência: o intervalo entre os dois relatórios mais
    recentes e distintos precisa ser compatível com a publicação semanal
    real do CFTC, dentro de uma tolerância generosa que absorve feriados
    sem mascarar uma cadência errada (ex.: só atualizando uma vez por
    mês)."""
    config = KNOWN_CONTRACTS[key]

    records = _call_or_skip(
        lambda: _client.query(
            DISAGGREGATED_COMBINED_DATASET_ID,
            select=DATE_FIELD,
            where=f"market_and_exchange_names = '{config.market_and_exchange_names}'",
            order=f"{DATE_FIELD} DESC",
            limit=10,
        )
    )
    assert records, f"{key} não retornou nenhum registro"

    distinct_dates: list[str] = []
    for record in records:
        raw = record.get(DATE_FIELD)
        if raw and raw not in distinct_dates:
            distinct_dates.append(raw)
        if len(distinct_dates) == 2:
            break

    assert len(distinct_dates) == 2, f"{key}: menos de duas datas distintas em {records}"

    newest = datetime.fromisoformat(distinct_dates[0])
    previous = datetime.fromisoformat(distinct_dates[1])
    gap_days = (newest - previous).days

    low, high = CADENCE_TOLERANCE_DAYS
    assert low <= gap_days <= high, (
        f"{key}: intervalo real de {gap_days} dias fora da faixa esperada "
        f"para cadência semanal ({low}-{high} dias)"
    )


def test_soybeans_cbot_open_interest_is_far_larger_than_mini_soybeans():
    """Regressão de relevância: o contrato registrado para soja
    (``SOYBEANS - CHICAGO BOARD OF TRADE``) precisa continuar sendo o
    contrato padrão CBOT, não o 'MINI SOYBEANS'. Em vez de comparar contra
    um limiar absoluto (que pode variar legitimamente ao longo do tempo),
    compara o open interest do contrato registrado contra o do mini,
    exigindo que ambos venham do mesmo ``report_date_as_yyyy_mm_dd`` — sem
    isso, uma comparação entre relatórios de datas diferentes não provaria
    nada sobre o filtro estar correto no relatório mais recente."""
    config = KNOWN_CONTRACTS["soybeans_cbot"]

    def _latest_report(market_and_exchange_names: str) -> dict[str, str]:
        records = _client.query(
            DISAGGREGATED_COMBINED_DATASET_ID,
            select=f"{DATE_FIELD},open_interest_all",
            where=f"market_and_exchange_names = '{market_and_exchange_names}'",
            order=f"{DATE_FIELD} DESC",
            limit=1,
        )
        assert records, f"nenhum registro retornado para {market_and_exchange_names!r}"
        return records[0]

    standard = _call_or_skip(lambda: _latest_report(config.market_and_exchange_names))
    mini = _call_or_skip(lambda: _latest_report("MINI SOYBEANS - CHICAGO BOARD OF TRADE"))

    assert standard[DATE_FIELD] == mini[DATE_FIELD], (
        f"contrato padrão ({standard[DATE_FIELD]}) e mini ({mini[DATE_FIELD]}) vieram de "
        "relatórios semanais diferentes — comparação de open interest não seria válida"
    )
    standard_oi = int(standard["open_interest_all"])
    mini_oi = int(mini["open_interest_all"])
    assert standard_oi > mini_oi * 5, (
        f"open_interest_all do contrato padrão ({standard_oi}) não é muito maior que o "
        f"do mini ({mini_oi}) no mesmo relatório — pode indicar que o filtro passou a "
        "casar o contrato errado"
    )
