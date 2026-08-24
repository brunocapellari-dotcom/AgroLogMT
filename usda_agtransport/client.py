from __future__ import annotations

from typing import Any

from socrata_connector import (
    ColumnMetadata,
    DatasetMetadata,
    SocrataApiError,
    SocrataClient as _SocrataClient,
    SocrataConnectionError,
)

_DEFAULT_BASE_URL = "https://agtransport.usda.gov"
_ALLOWED_HOSTS = frozenset({"agtransport.usda.gov"})


class SocrataClient(_SocrataClient):
    """AgTransport adapter sobre o cliente SODA canônico do AgroLog.

    Mantém a interface histórica do módulo USDA, mas concentra transporte,
    retries, validação de tipos e bloqueio de redirects em
    :mod:`socrata_connector`. O adapter restringe o host ao portal oficial
    do USDA e não expõe consultas de usuário final; cláusulas SoQL devem ser
    montadas apenas por código de fonte versionado.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = 20.0,
        max_retries: int = 3,
        app_token: str | None = None,
        session: Any | None = None,
    ) -> None:
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            app_token=app_token,
            session=session,
            allowed_hosts=_ALLOWED_HOSTS,
        )


def build_client(**kwargs: Any) -> SocrataClient:
    return SocrataClient(**kwargs)


__all__ = [
    "ColumnMetadata",
    "DatasetMetadata",
    "SocrataApiError",
    "SocrataClient",
    "SocrataConnectionError",
    "build_client",
]
