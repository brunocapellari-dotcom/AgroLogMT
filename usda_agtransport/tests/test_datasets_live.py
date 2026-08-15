"""Testes de integração reais contra a API SODA do AgTransport/USDA (Issue #20).

Fazem chamadas de rede de verdade. Pulam (``pytest.skip``) apenas quando o
problema é de conectividade (``SocrataConnectionError``), seguindo a mesma
regra do conector CKAN (Issue #19): indisponibilidade externa não deve
travar o build, mas um erro de contrato real (payload inesperado, HTTP
não-200) é uma regressão e deve falhar o teste.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from usda_agtransport.client import SocrataClient, SocrataConnectionError
from usda_agtransport.datasets import CADENCE_TOLERANCE_DAYS, KNOWN_DATASETS


def _client_or_skip() -> SocrataClient:
    client = SocrataClient(timeout=10.0, max_retries=1)
    try:
        client.dataset_metadata(next(iter(KNOWN_DATASETS.values())).dataset_id)
    except SocrataConnectionError as exc:
        pytest.skip(f"AgTransport inacessível deste ambiente (rede): {exc}")
    return client


@pytest.mark.parametrize("key", sorted(KNOWN_DATASETS))
def test_dataset_metadata_matches_registered_name_and_columns(key: str):
    client = _client_or_skip()
    config = KNOWN_DATASETS[key]

    metadata = client.dataset_metadata(config.dataset_id)

    assert metadata.name == config.name
    assert metadata.columns, f"{key} não retornou nenhuma coluna"
    field_names = {c.field_name for c in metadata.columns}
    assert config.date_field in field_names, (
        f"{key}: date_field {config.date_field!r} não existe nas colunas reais "
        f"({sorted(field_names)})"
    )


@pytest.mark.parametrize("key", sorted(KNOWN_DATASETS))
def test_cadence_matches_real_date_gap_between_recent_records(key: str):
    """Regressão de cadência: o intervalo entre as duas datas mais recentes
    e distintas precisa ser compatível com a cadência declarada em
    ``DatasetConfig.cadence``, dentro de uma tolerância generosa que
    absorve atraso normal de publicação sem mascarar uma cadência errada
    (ex.: registrada como trimestral quando na prática só atualiza uma vez
    por ano)."""
    client = _client_or_skip()
    config = KNOWN_DATASETS[key]

    records = client.query(
        config.dataset_id,
        select=config.date_field,
        order=f"{config.date_field} DESC",
        limit=50,
    )
    assert records, f"{key} não retornou nenhum registro"

    distinct_dates = []
    for record in records:
        raw = record.get(config.date_field)
        if raw and raw not in distinct_dates:
            distinct_dates.append(raw)
        if len(distinct_dates) == 2:
            break

    assert len(distinct_dates) == 2, f"{key}: menos de duas datas distintas em {records}"

    newest = datetime.fromisoformat(distinct_dates[0])
    previous = datetime.fromisoformat(distinct_dates[1])
    gap_days = (newest - previous).days

    low, high = CADENCE_TOLERANCE_DAYS[config.cadence]
    assert low <= gap_days <= high, (
        f"{key}: intervalo real de {gap_days} dias fora da faixa esperada "
        f"para cadência {config.cadence!r} ({low}-{high} dias)"
    )


def test_brazil_truck_route_rates_include_a_north_mt_origin():
    """Regressão de relevância: o dataset mais citado como direto ao MT
    precisa continuar tendo pelo menos uma rota com origem no MT."""
    client = _client_or_skip()
    config = KNOWN_DATASETS["brazil_soybean_truck_route_rates"]

    records = client.query(
        config.dataset_id, select="origin", where="origin like '%MT%'", limit=5
    )

    assert records, "nenhuma rota com origem no MT encontrada"
