"""Testes de integração reais contra a API NASA POWER (Issue #15).

Fazem chamadas de rede de verdade. Pulam (``pytest.skip``) sempre que o
problema é de conectividade (``NasaPowerConnectionError``), seguindo a
mesma regra já usada para CKAN (Issue #19), AgTransport/USDA (Issue #20)
e CFTC COT (Issue #14): indisponibilidade externa não deve travar o
build, mas um erro de contrato real (payload inesperado, HTTP não-200,
valores fisicamente implausíveis) é uma regressão e deve falhar o teste.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from nasa_power.client import NasaPowerConnectionError, build_client
from nasa_power.points import CORE_PARAMETERS, KNOWN_POINTS

_client = build_client(timeout=15.0, max_retries=1)
_START = "20260101"
_END = "20260105"


def _call_or_skip(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except NasaPowerConnectionError as exc:
        pytest.skip(f"NASA POWER inacessível deste ambiente (rede): {exc}")


@pytest.mark.parametrize("key", sorted(KNOWN_POINTS))
def test_daily_point_returns_all_core_parameters_with_plausible_values(key: str):
    point = KNOWN_POINTS[key]

    result = _call_or_skip(
        lambda: _client.daily_point(
            latitude=point.latitude,
            longitude=point.longitude,
            start=_START,
            end=_END,
            parameters=CORE_PARAMETERS,
        )
    )

    assert set(result.values.keys()) == set(CORE_PARAMETERS)
    for param in CORE_PARAMETERS:
        series = result.values[param]
        assert series, f"{key}/{param}: série vazia"
        non_null = [v for v in series.values() if v is not None]
        assert non_null, f"{key}/{param}: nenhum valor real (só fill_value/None)"

    temps = [v for v in result.values["T2M"].values() if v is not None]
    assert all(-10 <= t <= 50 for t in temps), f"{key}: T2M fora de faixa plausível: {temps}"

    precip = [v for v in result.values["PRECTOTCORR"].values() if v is not None]
    assert all(p >= 0 for p in precip), f"{key}: PRECTOTCORR negativo: {precip}"

    humidity = [v for v in result.values["RH2M"].values() if v is not None]
    assert all(0 <= h <= 100 for h in humidity), f"{key}: RH2M fora de 0-100: {humidity}"


def test_daily_point_returns_requested_date_range():
    point = KNOWN_POINTS["sorriso_mt"]

    result = _call_or_skip(
        lambda: _client.daily_point(
            latitude=point.latitude,
            longitude=point.longitude,
            start=_START,
            end=_END,
            parameters=("T2M",),
        )
    )

    dates = set(result.values["T2M"].keys())
    assert dates == {"20260101", "20260102", "20260103", "20260104", "20260105"}


def test_sources_confirm_modeled_reanalysis_not_ground_station():
    """Regressão de classificação de evidência (docs/DATA_GOVERNANCE.md):
    NASA POWER combina satélite (SYN1DEG) e reanálise/modelo (MERRA-2), não
    estação meteorológica terrestre — precisa continuar classificado como
    **estimado** ("valor calculado por modelo, coeficiente, aproximação ou
    hipótese explícita"), não **observado** ("valor obtido diretamente de
    fonte oficial, contratada ou autorizada"). Se a API passar a declarar
    só fontes de observação direta, essa distinção documentada mudaria e
    merece revisão manual, não silêncio."""
    point = KNOWN_POINTS["sorriso_mt"]

    result = _call_or_skip(
        lambda: _client.daily_point(
            latitude=point.latitude,
            longitude=point.longitude,
            start=_START,
            end=_END,
            parameters=("T2M",),
        )
    )

    assert "MERRA2" in result.sources or "SYN1DEG" in result.sources, (
        f"fontes declaradas mudaram para {result.sources!r} — revisar classificação "
        "observado/modelado em docs/sources/nasa_power/README.md"
    )


def test_unknown_parameter_raises_api_error_not_silent_empty_result():
    from nasa_power.client import NasaPowerApiError

    point = KNOWN_POINTS["sorriso_mt"]
    with pytest.raises(NasaPowerApiError):
        _call_or_skip(
            lambda: _client.daily_point(
                latitude=point.latitude,
                longitude=point.longitude,
                start=_START,
                end=_END,
                parameters=("NOT_A_REAL_PARAMETER",),
            )
        )
