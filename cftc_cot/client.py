from __future__ import annotations

import requests

from socrata_connector import SocrataApiError, SocrataClient, SocrataConnectionError

CFTC_BASE_URL = "https://publicreporting.cftc.gov"


def build_client(
    *,
    timeout: float = 20.0,
    max_retries: int = 3,
    app_token: str | None = None,
    session: requests.Session | None = None,
) -> SocrataClient:
    """Cliente SODA (Socrata) já apontado para o host oficial do CFTC Public Reporting.

    Não aceita ``base_url`` como parâmetro — o host é sempre
    :data:`CFTC_BASE_URL`, para impedir que um chamador aponte
    acidentalmente (ou de propósito) o cliente para outro host.
    """
    return SocrataClient(
        base_url=CFTC_BASE_URL,
        timeout=timeout,
        max_retries=max_retries,
        app_token=app_token,
        session=session,
    )


__all__ = [
    "SocrataApiError",
    "SocrataClient",
    "SocrataConnectionError",
    "CFTC_BASE_URL",
    "build_client",
]
