from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_DEFAULT_TIMEOUT = 20.0
_MAX_LIMIT = 50000  # teto da API SODA (Socrata) por requisição


class SocrataApiError(RuntimeError):
    """Erro retornado por uma API SODA (Socrata)."""


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
    """Cliente somente leitura genérico para APIs SODA (Socrata).

    Plataforma usada por vários portais de dados oficiais (ex.:
    ``agtransport.usda.gov``, ``publicreporting.cftc.gov``, ``data.gov`` e
    diversos portais estaduais dos EUA). Este cliente fala apenas com o
    host declarado em ``base_url`` — qualquer host fora de ``allowed_hosts``
    (por padrão, exatamente o host de ``base_url``) é recusado no
    construtor. Redirects não são seguidos (``allow_redirects=False``): um
    ``3xx`` inesperado vira :class:`SocrataApiError` em vez de ser seguido
    para outro host, o que evitaria vazar ``X-App-Token`` para um destino
    diferente do declarado.

    ``select``/``where``/``order`` em :meth:`query` são cláusulas SoQL
    literais — este cliente não faz nenhuma sanitização ou parametrização
    delas (a API SODA não oferece um mecanismo de parâmetros vinculados
    para SoQL). Por isso, ele é seguro apenas para consultas montadas por
    código próprio de fonte (ex.: ``datasets.py`` de cada módulo
    consumidor); nunca repasse texto de usuário final diretamente para
    essas cláusulas. Superfícies voltadas a usuário final (como o AgroLog
    Gateway) devem continuar usando parâmetros de query vinculados
    (``ScalarQueryParameter`` do BigQuery, por exemplo), não este cliente.

    Extraído de ``usda_agtransport.client`` (Issue #20) e ``cftc_cot.client``
    (Issue #14), que implementavam a mesma lógica de forma duplicada. Módulos
    de fonte devem consumir este pacote em vez de reimplementar um cliente
    Socrata próprio.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 3,
        app_token: str | None = None,
        session: requests.Session | None = None,
        allowed_hosts: frozenset[str] | None = None,
    ) -> None:
        parts = urlsplit(base_url)
        if parts.scheme != "https":
            raise ValueError(f"base_url deve ser https: {base_url!r}.")
        hosts = allowed_hosts if allowed_hosts is not None else frozenset({parts.hostname})
        if parts.hostname not in hosts:
            raise ValueError(f"base_url deve usar um host permitido ({sorted(hosts)}): {base_url!r}.")
        self._base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.app_token = app_token
        self._session = session or _build_session(max_retries)

    @property
    def base_url(self) -> str:
        """Host validado no construtor — somente leitura.

        Exposto como propriedade (não atributo mutável) para que a garantia
        de "só fala com o host declarado" não possa ser contornada
        reatribuindo ``client.base_url`` depois da validação.
        """
        return self._base_url

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

        Ver o aviso de segurança na docstring da classe sobre
        ``select``/``where``/``order``: são cláusulas SoQL literais, sem
        sanitização — só devem ser montadas por código próprio de fonte,
        nunca a partir de texto de usuário final.
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
