"""Testes de integração reais contra portais CKAN oficiais (Issue #19).

Fazem chamadas de rede de verdade a ANEEL e ANTT Dados Abertos. Pulam
(``pytest.skip``) apenas quando o problema é de conectividade
(``CkanConnectionError`` — DNS/timeout/conexão recusada), conforme a regra
do projeto de que testes dependentes de dados reais precisam de um caminho
configurável/externo em vez de travar o build por indisponibilidade
externa. Um erro de contrato da API (payload inesperado, ``success: false``,
HTTP não-200) é uma regressão real e deve falhar o teste, não ser
silenciado como skip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ckan_connector.client import CkanClient, CkanConnectionError
from ckan_connector.portals import KNOWN_PORTALS


def _client_or_skip(portal_name: str) -> CkanClient:
    portal = KNOWN_PORTALS[portal_name]
    client = CkanClient(portal.base_url, timeout=10.0, max_retries=1)
    try:
        client.package_list()
    except CkanConnectionError as exc:
        pytest.skip(f"Portal {portal_name} inacessível deste ambiente (rede): {exc}")
    return client


@pytest.mark.parametrize("portal_name", sorted(KNOWN_PORTALS))
def test_package_list_returns_real_datasets(portal_name: str):
    client = _client_or_skip(portal_name)
    packages = client.package_list()
    assert packages, f"{portal_name} não retornou nenhum dataset"


@pytest.mark.parametrize("portal_name", sorted(KNOWN_PORTALS))
def test_package_show_returns_resources_for_first_dataset(portal_name: str):
    client = _client_or_skip(portal_name)
    packages = client.package_list()
    first_package = packages[0]

    resources = client.list_resources(first_package)

    # Nem todo dataset tem recursos com URL válida, mas a chamada deve ser
    # bem-sucedida e devolver uma lista (mesmo que vazia).
    assert isinstance(resources, list)


def test_download_resource_from_aneel_records_real_hash_and_size(tmp_path: Path):
    client = _client_or_skip("aneel")
    packages = client.package_list()

    downloaded = None
    for package_id in packages[:25]:
        resources = client.list_resources(package_id)
        small_resources = [r for r in resources if r.format in {"CSV", "JSON", "XML"}]
        if not small_resources:
            continue
        try:
            downloaded = client.download_resource(small_resources[0], tmp_path)
        except CkanConnectionError:
            continue
        break

    if downloaded is None:
        pytest.skip("Nenhum recurso CSV/JSON/XML pequeno encontrado nos primeiros datasets da ANEEL.")

    assert downloaded.dest_path.exists()
    assert downloaded.size_bytes == downloaded.dest_path.stat().st_size
    assert len(downloaded.sha256) == 64
    assert downloaded.collected_at
