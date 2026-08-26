from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

BASE_URL = "https://api-comexstat.mdic.gov.br"
ALLOWED_HOST = "api-comexstat.mdic.gov.br"
SOURCE_ID = "mdic_comexstat_api"


@dataclass(frozen=True)
class ComexUpdate:
    updated: str | None
    year: int | None
    month: int | None

    @property
    def competence(self) -> str | None:
        if self.year is None or self.month is None:
            return None
        return f"{self.year:04d}-{self.month:02d}"


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.username or parsed.password:
        raise ValueError("ComexStat API deve usar exclusivamente https://api-comexstat.mdic.gov.br")
    return base_url.rstrip("/")


class ComexStatApiClient:
    """Cliente read-only da API pública ComexStat com TLS obrigatório e host travado.

    Esta é a rota operacional prioritária do AgroLog MT para consultas mensais e
    incrementais. Os CSVs abertos permanecem como rota de backfill/reconciliação em
    grande volume, nunca como requisito para a atualização operacional da API.

    Não existe fallback ``verify=False``. A sessão padrão usa retries limitados para
    429/5xx, respeita ``Retry-After`` e bloqueia redirects para evitar mudança silenciosa
    de host ou transporte.
    """

    def __init__(self, *, base_url: str = BASE_URL, timeout: int = 120, session: Any | None = None) -> None:
        self.base_url = _validate_base_url(base_url)
        self.timeout = timeout
        if timeout < 1:
            raise ValueError("timeout deve ser positivo")
        if session is None:
            import requests
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            session = requests.Session()
            retry = Retry(
                total=5,
                connect=3,
                read=3,
                status=5,
                backoff_factor=2.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET", "POST"}),
                respect_retry_after_header=True,
                raise_on_status=False,
            )
            session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session = session
        self.session.headers.update(
            {
                "User-Agent": "AgroLogMT/0.1 (+ComexStat API)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            raise ValueError("path ComexStat deve iniciar com /")
        url = f"{self.base_url}{path}"
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST:
            raise ValueError("host ComexStat fora da allowlist")
        return url

    @staticmethod
    def _validate_payload(payload: dict[str, Any]) -> None:
        if payload.get("flow") not in {"export", "import"}:
            raise ValueError("flow deve ser export ou import")
        if not isinstance(payload.get("monthDetail"), bool):
            raise ValueError("monthDetail deve ser booleano")
        period = payload.get("period")
        if not isinstance(period, dict) or not period.get("from") or not period.get("to"):
            raise ValueError("period.from e period.to são obrigatórios")
        if str(period["from"]) > str(period["to"]):
            raise ValueError("period.from não pode ser posterior a period.to")
        for key in ("filters", "details", "metrics"):
            if key not in payload or not isinstance(payload[key], list):
                raise ValueError(f"{key} deve ser lista")
        if not payload["metrics"]:
            raise ValueError("metrics não pode ser vazio")
        for item in payload["filters"]:
            if not isinstance(item, dict) or not isinstance(item.get("filter"), str) or not isinstance(item.get("values"), list):
                raise ValueError("filter inválido")
            if not item["values"]:
                raise ValueError("filter.values não pode ser vazio")

    def _json_response(self, response: Any) -> dict[str, Any]:
        status = int(getattr(response, "status_code", 200))
        if 300 <= status < 400:
            raise RuntimeError(f"ComexStat API retornou redirect HTTP {status}; redirect automático é bloqueado")
        response.raise_for_status()
        observed = urlparse(response.url)
        if observed.scheme != "https" or observed.hostname != ALLOWED_HOST:
            raise RuntimeError("ComexStat API respondeu por host/transporte não autorizado")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("ComexStat API retornou JSON não-objeto")
        if payload.get("success") is False:
            raise RuntimeError(f"ComexStat API reportou falha: {payload.get('message')}")
        return payload

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(
            self._url(path), params=params or {"language": "pt"}, timeout=self.timeout,
            allow_redirects=False,
        )
        return self._json_response(response)

    def post(self, path: str, payload: dict[str, Any], *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._validate_payload(payload)
        response = self.session.post(
            self._url(path), params=params or {"language": "pt"}, json=payload,
            timeout=self.timeout, allow_redirects=False,
        )
        return self._json_response(response)

    def last_update(self) -> ComexUpdate:
        payload = self.get("/general/dates/updated")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            raise RuntimeError("ComexStat /dates/updated sem objeto data")
        year = int(data["year"]) if data.get("year") not in {None, ""} else None
        month = int(data["monthNumber"]) if data.get("monthNumber") not in {None, ""} else None
        if month is not None and not 1 <= month <= 12:
            raise RuntimeError("ComexStat /dates/updated retornou mês inválido")
        return ComexUpdate(updated=data.get("updated"), year=year, month=month)

    def available_years(self) -> tuple[int, int]:
        payload = self.get("/general/dates/years")
        data = payload.get("data") or {}
        if not isinstance(data, dict) or data.get("min") is None or data.get("max") is None:
            raise RuntimeError("ComexStat /dates/years sem min/max")
        return int(data["min"]), int(data["max"])

    def filters(self, *, module: str = "general") -> dict[str, Any]:
        if module not in {"general", "cities"}:
            raise ValueError("module deve ser general ou cities")
        return self.get(f"/{module}/filters")

    def details(self, *, module: str = "general") -> dict[str, Any]:
        if module not in {"general", "cities"}:
            raise ValueError("module deve ser general ou cities")
        return self.get(f"/{module}/details")

    def metrics(self, *, module: str = "general") -> dict[str, Any]:
        if module not in {"general", "cities"}:
            raise ValueError("module deve ser general ou cities")
        return self.get(f"/{module}/metrics")

    def query(self, payload: dict[str, Any], *, module: str = "general") -> dict[str, Any]:
        if module not in {"general", "cities"}:
            raise ValueError("module deve ser general ou cities")
        return self.post(f"/{module}", payload)

    def general(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.query(payload, module="general")

    def cities(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.query(payload, module="cities")

    @staticmethod
    def data_list(response: dict[str, Any]) -> list[dict[str, Any]]:
        data = response.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            rows = data.get("list")
            if rows is None:
                return []
            if not isinstance(rows, list):
                raise RuntimeError("ComexStat response.data.list não é lista")
            return [item for item in rows if isinstance(item, dict)]
        raise RuntimeError("ComexStat response.data ausente ou inválido")


def trade_payload(
    *,
    flow: str,
    start: str,
    end: str,
    filters: list[dict[str, Any]],
    details: list[str],
    metrics: list[str] | None = None,
    month_detail: bool = True,
) -> dict[str, Any]:
    payload = {
        "flow": flow,
        "monthDetail": bool(month_detail),
        "period": {"from": start, "to": end},
        "filters": filters,
        "details": details,
        "metrics": ["metricFOB", "metricKG"] if metrics is None else metrics,
    }
    ComexStatApiClient._validate_payload(payload)
    return payload


def soybean_export_payload(
    *,
    start: str,
    end: str,
    month_detail: bool = True,
    state_code: int | None = None,
    include_logistics: bool = True,
) -> dict[str, Any]:
    """Consulta operacional de soja em grão pela API ComexStat.

    NCM 12011000 = soja para semeadura; 12019000 = outras sojas. ``state`` é UF do
    produto na semântica ComexStat. Para Mato Grosso use ``state_code=51``.

    Quando ``include_logistics`` é verdadeiro, a consulta preserva país, via e URF
    para permitir leitura dos corredores de exportação sem confundir programação
    portuária com comércio efetivamente registrado.
    """
    filters: list[dict[str, Any]] = [{"filter": "ncm", "values": [12011000, 12019000]}]
    if state_code is not None:
        filters.append({"filter": "state", "values": [int(state_code)]})
    details = ["ncm", "state", "country"]
    if include_logistics:
        details.extend(["via", "urf"])
    return trade_payload(
        flow="export",
        start=start,
        end=end,
        month_detail=month_detail,
        filters=filters,
        details=details,
        metrics=["metricFOB", "metricKG"],
    )
