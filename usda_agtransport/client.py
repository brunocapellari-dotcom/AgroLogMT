from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_DEFAULT_TIMEOUT = 20.0
_DEFAULT_BASE_URL = "https://agtransport.usda.gov"
_ALLOWED_HOSTS = frozenset({"agtransport.usda.gov"})
_MAX_LIMIT = 50000  # teto da API SODA (Socrata) por requisição


class SocrataApiError(RuntimeError):
    """Erro retornado pela API SODA (Socrata) do AgTransport/USDA."""


class SocrataConnectionError(SocrataApiError):
    """Subconjunto de :class:`SocrataApiError` por falha de rede/DNS.

    Mantido separado para que quem chama (ex.: testes de integração) possa
    diferenciar "plataforma inacessível deste ambiente" de "a API respondeu
    com um erro" — o segundo caso é uma regressão real e não deve virar skip.
    """


@dataclass(frozen=True)
class ColumnMetadata:
    field_name: str
    data_type: str
    display_name: str


@dataclass(frozen=True)
class DatasetMetadata:
    """Metadados de um dataset tabular, conforme ``/api/views/{id}.json``."""

    dataset_id: str
    name: str
    description: str
    attribution: str
    license: str | None
    category: str | None
    rows_updated_at: datetime | None
    columns: list[ColumnMetadata]
    raw: dict[str, Any] = field(repr=False)


def _build_session(max_retries: int) -> requests.Session:
    retry = Retry(
        total=max_retries,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    return session


class SocrataClient:
    """Cliente somente leitura para a API SODA (Socrata) do AgTransport/USDA.

    Fala apenas com o host oficial ``agtransport.usda.gov`` — ``base_url``
    só existe para injetar um host de teste equivalente; qualquer host fora
    de :data:`_ALLOWED_HOSTS` é recusado no construtor. Redirects não são
    seguidos (``allow_redirects=False``): esta API não deveria redirecionar
    em uso normal, e não seguir evita vazar ``X-App-Token`` para um host
    diferente caso um dia haja um redirect inesperado.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 3,
        app_token: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        parts = urlsplit(base_url)
        if parts.scheme != "https" or parts.hostname not in _ALLOWED_HOSTS:
            raise ValueError(
                f"base_url deve ser https e um host permitido ({sorted(_ALLOWED_HOSTS)}): {base_url!r}."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.app_token = app_token
        self._session = session or _build_session(max_retries)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        return headers

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise SocrataConnectionError(f"Falha de rede ao acessar {url}: {exc}") from exc

        with response:
            if response.status_code in (301, 302, 303, 307, 308):
                raise SocrataApiError(
                    f"{url} respondeu com redirect HTTP {response.status_code}, não seguido."
                )
            if response.status_code != 200:
                raise SocrataApiError(
                    f"{url} retornou HTTP {response.status_code}: {response.text[:300]!r}"
                )
            try:
                return response.json()
            except ValueError as exc:
                raise SocrataApiError(f"{url} não retornou JSON válido.") from exc

    def dataset_metadata(self, dataset_id: str) -> DatasetMetadata:
        """Metadados de um dataset: colunas, licença, atribuição, atualização."""
        payload = self._get(f"/api/views/{dataset_id}.json")
        if not isinstance(payload, dict):
            raise SocrataApiError(f"Metadados de {dataset_id} vieram em formato inesperado.")

        columns_raw = payload.get("columns") or []
        columns = [
            ColumnMetadata(
                field_name=str(c.get("fieldName")),
                data_type=str(c.get("dataTypeName") or ""),
                display_name=str(c.get("name") or ""),
            )
            for c in columns_raw
            if isinstance(c, dict) and c.get("fieldName")
        ]

        rows_updated_at_raw = payload.get("rowsUpdatedAt")
        rows_updated_at = (
            datetime.fromtimestamp(rows_updated_at_raw, tz=timezone.utc)
            if isinstance(rows_updated_at_raw, (int, float))
            else None
        )

        return DatasetMetadata(
            dataset_id=dataset_id,
            name=str(payload.get("name") or ""),
            description=str(payload.get("description") or ""),
            attribution=str(payload.get("attribution") or ""),
            license=payload.get("license"),
            category=payload.get("category"),
            rows_updated_at=rows_updated_at,
            columns=columns,
            raw=payload,
        )

    def query(
        self,
        dataset_id: str,
        *,
        select: str | None = None,
        where: str | None = None,
        order: str | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Consulta registros via SODA (``$select``/``$where``/``$order``/``$limit``/``$offset``).

        ``select``/``where``/``order`` são cláusulas SoQL literais definidas
        por quem chama esta função — assim como no cliente CKAN (Issue #19),
        este módulo não expõe entrada de usuário final a essas cláusulas;
        quem monta a consulta é sempre código próprio de fonte.
        """
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= _MAX_LIMIT:
            raise ValueError(f"limit deve ser um inteiro entre 1 e {_MAX_LIMIT}.")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("offset deve ser um inteiro não negativo.")

        params: dict[str, Any] = {"$limit": limit, "$offset": offset}
        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order

        payload = self._get(f"/resource/{dataset_id}.json", params=params)
        if not isinstance(payload, list) or not all(isinstance(r, dict) for r in payload):
            raise SocrataApiError(f"Consulta a {dataset_id} não retornou uma lista de registros.")
        return payload
