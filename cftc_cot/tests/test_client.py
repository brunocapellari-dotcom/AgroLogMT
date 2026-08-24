"""Testes específicos do CFTC sobre socrata_connector.SocrataClient.

O comportamento genérico do cliente Socrata (allowlist de host, retries,
tratamento de erro/redirect, montagem de parâmetros SoQL) é testado uma
única vez em ``socrata_connector/tests/test_client.py`` — este arquivo
cobre apenas o que é específico deste módulo: que ``build_client()`` está
travado no host oficial do CFTC e não pode ser redirecionado para outro
host.
"""

from __future__ import annotations

from unittest.mock import Mock

from cftc_cot.client import CFTC_BASE_URL, build_client


def test_build_client_points_to_cftc_host():
    client = build_client(session=Mock())
    assert client.base_url == CFTC_BASE_URL == "https://publicreporting.cftc.gov"


def test_build_client_does_not_accept_a_base_url_override():
    # build_client() não expõe base_url como parâmetro — só forma de
    # garantir isso é confirmar que a assinatura não aceita a palavra-chave.
    import inspect

    params = inspect.signature(build_client).parameters
    assert "base_url" not in params
