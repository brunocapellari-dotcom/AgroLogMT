from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

NASA_POWER_BASE_URL = "https://power.larc.nasa.gov"
_ALLOWED_HOST = "power.larc.nasa.gov"
_DEFAULT_TIMEOUT = 20.0
_VALID_COMMUNITIES = frozenset({"ag", "sb", "re"})
_DATE_LEN = 8  # formato YYYYMMDD exigido pela API


class NasaPowerApiError(RuntimeError):
    """Erro retornado pela API NASA POWER."""


class NasaPowerConnectionError(NasaPowerApiError):
    """Subconjunto de :class:`NasaPowerApiError` por falha de rede/DNS.

    Mantido separado para que quem chama (ex.: testes de integração) possa
    diferenciar "plataforma inacessível deste ambiente" de "a API
    respondeu com um erro de contrato" — o segundo caso é uma regressão
    real e não deve virar skip.
    """


@dataclass(frozen=True)
class DailyPointResult:
    """Resultado de uma consulta ``temporal/daily/point`` já normalizado.

    ``values`` mapeia parâmetro -> data (``YYYYMMDD``) -> valor, com
    ``None`` no lugar de qualquer leitura igual a ``fill_value`` (a API usa
    ``-999.0`` como sentinela de dado ausente; não normalizar isso faria
    "sem dado" ser lido como uma temperatura de -999°C).
    """

    latitude: float
    longitude: float
    elevation_m: float | None
    sources: tuple[str, ...]
    fill_value: float
    units: dict[str, str]
    values: dict[str, dict[str, float | None]]
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


def _extract_error_message(status_code: int, body: Any) -> str:
    # A API NASA POWER usa dois formatos de erro distintos observados
    # nesta avaliação: validação de tipo/faixa (pydantic, ex. latitude
    # fora de [-90, 90]) responde {"detail": [...]}; parâmetro
    # desconhecido responde {"header": "...", "messages": [...]}.
    if isinstance(body, dict):
        if isinstance(body.get("messages"), list) and body["messages"]:
            return "; ".join(str(m) for m in body["messages"])
        if isinstance(body.get("detail"), list) and body["detail"]:
            parts = []
            for item in body["detail"]:
                if isinstance(item, dict) and "msg" in item:
                    loc_raw = item.get("loc")
                    loc = ".".join(str(p) for p in loc_raw) if isinstance(loc_raw, (list, tuple)) else ""
                    parts.append(f"{loc}: {item['msg']}" if loc else str(item["msg"]))
            if parts:
                return "; ".join(parts)
    return f"HTTP {status_code}"


class NasaPowerClient:
    """Cliente somente leitura para a API NASA POWER (``temporal/daily/point``).

    Fala apenas com ``power.larc.nasa.gov`` — o host é fixo em
    :data:`NASA_POWER_BASE_URL` e não é configurável pelo chamador, para
    impedir que o cliente aponte acidentalmente (ou de propósito) para
    outro host. Não segue redirects (``allow_redirects=False``).

    Não requer chave/token: os endpoints usados são de leitura pública.
    Cobre só o endpoint ``temporal/daily/point`` avaliado na Issue #15;
    ``temporal/monthly``/``temporal/climatology``/``regional`` ficam fora
    do escopo desta avaliação/PoC.
    """

    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        # Comparação da URL inteira (esquema+host+porta), não só do
        # hostname: uma constante alterada para http:// ou para uma porta
        # não padrão também deve ser recusada, não só um host diferente.
        if NASA_POWER_BASE_URL != f"https://{_ALLOWED_HOST}":
            raise ValueError(f"NASA_POWER_BASE_URL inesperado: {NASA_POWER_BASE_URL!r}.")
        # Copiado para um atributo de instância (não relido do módulo em
        # cada requisição): reatribuir o nome de módulo
        # ``nasa_power.client.NASA_POWER_BASE_URL`` depois de construir o
        # cliente não pode redirecionar requisições já em curso para outro
        # host.
        self._base_url = NASA_POWER_BASE_URL
        self.timeout = timeout
        self._session = session or _build_session(max_retries)

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        url = f"{self._base_url}{path}"
        try:
            response = self._session.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise NasaPowerConnectionError(f"Falha de rede ao acessar {url}: {exc}") from exc

        with response:
            if response.status_code in (301, 302, 303, 307, 308):
                raise NasaPowerApiError(
                    f"{url} respondeu com redirect HTTP {response.status_code}, não seguido."
                )
            if response.status_code != 200:
                try:
                    body = response.json()
                    detail = _extract_error_message(response.status_code, body)
                except (ValueError, TypeError, KeyError, AttributeError):
                    # Corpo de erro em formato inesperado (não-JSON, ou JSON
                    # com um shape diferente do documentado) não deve
                    # impedir de reportar ao menos o status HTTP real.
                    detail = response.text[:300]
                raise NasaPowerApiError(f"{url} retornou HTTP {response.status_code}: {detail}")
            try:
                return response.json()
            except ValueError as exc:
                raise NasaPowerApiError(f"{url} não retornou JSON válido.") from exc

    def daily_point(
        self,
        *,
        latitude: float,
        longitude: float,
        start: str,
        end: str,
        parameters: Sequence[str],
        community: str = "ag",
    ) -> DailyPointResult:
        """Série diária de um ponto (lat/lon) para os parâmetros pedidos.

        ``start``/``end`` no formato ``YYYYMMDD`` (mesmo formato exigido
        pela API). ``community`` segue o enum da própria API
        (``ag``/``sb``/``re``); o padrão ``ag`` (agroclimatology) é o
        relevante para o AgroLog.
        """
        for value, name, low, high in ((latitude, "latitude", -90.0, 90.0), (longitude, "longitude", -180.0, 180.0)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} deve ser um número finito: {value!r}.")
            if not low <= value <= high:
                raise ValueError(f"{name} deve estar entre {low} e {high}: {value!r}.")
        if not isinstance(community, str) or community.lower() not in _VALID_COMMUNITIES:
            raise ValueError(f"community deve ser um de {sorted(_VALID_COMMUNITIES)}: {community!r}.")
        if isinstance(parameters, str) or not isinstance(parameters, Sequence) or not parameters:
            raise ValueError(f"parameters deve ser uma sequência não vazia de nomes: {parameters!r}.")
        for p in parameters:
            if not isinstance(p, str) or not p.strip():
                raise ValueError(f"cada item de parameters deve ser um nome não vazio: {p!r}.")
        for value, name in ((start, "start"), (end, "end")):
            if not isinstance(value, str) or len(value) != _DATE_LEN:
                raise ValueError(f"{name} deve estar no formato YYYYMMDD: {value!r}.")
            try:
                datetime.strptime(value, "%Y%m%d")
            except ValueError as exc:
                raise ValueError(f"{name} não é uma data válida (YYYYMMDD): {value!r}.") from exc
        if end < start:
            raise ValueError(f"end ({end!r}) não pode ser anterior a start ({start!r}).")

        params = {
            "parameters": ",".join(parameters),
            "community": community.upper(),
            "longitude": longitude,
            "latitude": latitude,
            "start": start,
            "end": end,
            "format": "JSON",
        }
        payload = self._get("/api/temporal/daily/point", params)
        return self._parse(payload)

    @staticmethod
    def _parse(payload: dict[str, Any]) -> DailyPointResult:
        if not isinstance(payload, dict):
            raise NasaPowerApiError("Resposta da API NASA POWER não é um objeto JSON.")
        # Todo o parsing (não só a extração inicial de chaves) fica sob a
        # mesma proteção: um payload com schema inesperado (coordinates
        # vazio, header nulo, série que não é um dict) deve virar
        # NasaPowerApiError, não uma exceção nativa (KeyError/TypeError/
        # ValueError/AttributeError) vazando para quem chama.
        try:
            geometry = payload["geometry"]
            header = payload["header"]
            parameter_values = payload["properties"]["parameter"]

            fill_value = float(header.get("fill_value", -999.0))
            longitude, latitude, *elevation = geometry.get("coordinates", [None, None])
            units_meta = payload.get("parameters") or {}

            values: dict[str, dict[str, float | None]] = {}
            for param_name, series in parameter_values.items():
                values[param_name] = {
                    date: (None if v == fill_value else v) for date, v in series.items()
                }

            result = DailyPointResult(
                latitude=latitude,
                longitude=longitude,
                elevation_m=elevation[0] if elevation else None,
                sources=tuple(header.get("sources") or ()),
                fill_value=fill_value,
                units={name: meta.get("units", "") for name, meta in units_meta.items()},
                values=values,
                raw=payload,
            )
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise NasaPowerApiError(f"Resposta da API NASA POWER em formato inesperado: {exc}") from exc

        return result


def build_client(
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    max_retries: int = 3,
    session: requests.Session | None = None,
) -> NasaPowerClient:
    """Cliente NASA POWER já travado no host oficial (sem parâmetro ``base_url``)."""
    return NasaPowerClient(timeout=timeout, max_retries=max_retries, session=session)


__all__ = [
    "NASA_POWER_BASE_URL",
    "NasaPowerApiError",
    "NasaPowerConnectionError",
    "NasaPowerClient",
    "DailyPointResult",
    "build_client",
]
