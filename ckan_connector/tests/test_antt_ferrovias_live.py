"""Teste de integração real específico do dataset SIADE/ANTT (Issue #17).

Complementa ``test_portals_live.py`` (genérico, Issue #19): aqui a
verificação é sobre o dataset concreto que a avaliação em
``docs/sources/antt_ferrovias/README.md`` usa como fonte principal de
dados ferroviários — não apenas "o portal responde", mas "o dataset e o
schema que a avaliação documentou continuam existindo e acessíveis". Pula
(``pytest.skip``) apenas em falha de conectividade, pela mesma regra do
projeto de não travar o build por indisponibilidade externa.
"""

from __future__ import annotations

import re

import pytest

from ckan_connector.client import CkanClient, CkanConnectionError
from ckan_connector.portals import KNOWN_PORTALS

_SIADE_PACKAGE_ID = (
    "sistema-de-acompanhamento-do-desempenho-operacional-das-concessionarias-siade"
)
_EXPECTED_CSV_COLUMNS = (
    "Mes_Ano",
    "Ferrovia",
    "Mercadoria_ANTT",
    "Estacao_Origem",
    "UF_Origem",
    "Estacao_Destino",
    "UF_Destino",
    "TU",
    "TKU",
)
_TRAILING_YEAR_RE = re.compile(r"(\d{4})\s*$")


def _client_or_skip() -> CkanClient:
    portal = KNOWN_PORTALS["antt"]
    client = CkanClient(portal.base_url, timeout=15.0, max_retries=1)
    try:
        client.package_list()
    except CkanConnectionError as exc:
        pytest.skip(f"Portal ANTT inacessível deste ambiente (rede): {exc}")
    return client


def test_siade_package_exists_with_cc_by_license():
    client = _client_or_skip()

    try:
        package = client.package_show(_SIADE_PACKAGE_ID)
    except CkanConnectionError as exc:
        pytest.skip(f"package_show do SIADE falhou por rede: {exc}")

    assert package.get("license_id") == "cc-by"


def test_siade_has_producao_origem_destino_resource_with_documented_columns(tmp_path):
    client = _client_or_skip()

    try:
        resources = client.list_resources(_SIADE_PACKAGE_ID)
    except CkanConnectionError as exc:
        pytest.skip(f"list_resources do SIADE falhou por rede: {exc}")

    # "Mais recente" é decidido pelo ano ao final do nome do recurso (ex.
    # "Produção Origem Destino 2025"), não por ordenação lexicográfica do
    # nome inteiro — o portal já reordenou/renomeou recursos no passado
    # (achado da revisão adversarial desta Issue), então comparar a string
    # completa seria frágil.
    csv_resources = []
    for resource in resources:
        if resource.format != "CSV" or "Produção Origem Destino" not in resource.name:
            continue
        year_match = _TRAILING_YEAR_RE.search(resource.name)
        if year_match:
            csv_resources.append((int(year_match.group(1)), resource))
    assert csv_resources, "Nenhum recurso CSV de 'Produção Origem Destino <ano>' encontrado no SIADE."

    _, most_recent = max(csv_resources, key=lambda pair: pair[0])
    try:
        record = client.download_resource(most_recent, tmp_path)
    except CkanConnectionError as exc:
        pytest.skip(f"Download do recurso SIADE falhou por rede: {exc}")

    raw = record.dest_path.read_bytes()

    header = raw.split(b"\n", 1)[0].decode("cp1252").strip()
    assert header.split(";") == list(_EXPECTED_CSV_COLUMNS)

    # Confirma a alegação de encoding do README (cp1252, não UTF-8) sobre o
    # arquivo inteiro, não só o cabeçalho ASCII: cp1252 decodifica sem
    # erro (evidência de que é o encoding certo) e UTF-8 estrito falha —
    # o arquivo real não é UTF-8 válido.
    raw.decode("cp1252")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")
