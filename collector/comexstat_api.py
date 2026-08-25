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


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname != ALLOWED_HOST or parsed.username or parsed.password:
        raise ValueError("ComexStat API deve usar exclusivamente https://api-comexstat.mdic.gov.br")
    return base_url.rstrip("/")


class ComexStatApiClient:
    """Cliente read-only da API pública ComexStat com TLS obrigatório e host travado.

    Não existe fallback `verify=False`. O cliente serve como rota operacional agregada;
    os CSVs brutos continuam sendo a fonte preferida para backfill integral quando o
    runtime conseguir validar a cadeia TLS do host de arquivos.
    """

    def __init__(self, *, base_url: str = BASE_URL, timeout: int = 120, session: Any | None = None) -> None:
        self.base_url = _validate_base_url(base_url)
        self.timeout = timeout
        if timeout < 1:
            raise ValueError("timeout deve ser positivo")
        if session is None:
            import requests
            session = requests.Session()
        self.session = session
        self.session.headers.update({"User-Agent": "AgroLogMT/0.1 (+ComexStat API)", "Accept": "application/json"})

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
        period = payload.get("period")
        if not isinstance(period, dict) or not period.get("from") or not period.get("to"):
            raise ValueError("period.from e period.to são obrigatórios")
        for key in ("filters", "details", "metrics"):
            if key not in payload or not isinstance(payload[key], list):
                raise ValueError(f"{key} deve ser lista")
        for item in payload["filters"]:
            if not isinstance(item, dict) or not isinstance(item.get("filter"), str) or not isinstance(item.get("values"), list):
                raise ValueError("filter inválido")

    def _json_response(self, response: Any) -> dict[str, Any]:
        response.raise_for_status()
        observed = urlparse(response.url)
        if observed.scheme != "https" or observed.hostname != ALLOWED_HOST:
            raise RuntimeError("ComexStat API redirecionou para host/transporte não autorizado")
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
        return ComexUpdate(updated=data.get("updated"), year=year, month=month)

    def available_years(self) -> tuple[int, int]:
        payload = self.get("/general/dates/years")
        data = payload.get("data") or {}
        if not isinstance(data, dict) or data.get("min") is None or data.get("max") is None:
            raise RuntimeError("ComexStat /dates/years sem min/max")
        return int(data["min"]), int(data["max"])

    def general(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post("/general", payload)


def soybean_export_payload(*, start: str, end: str, month_detail: bool = True) -> dict[str, Any]:
    """Consulta operacional pequena para soja em grão, preservando UF de produto.

    NCM 12011000 = soja para semeadura; 12019000 = outras sojas.
    O campo state é SG_UF_NCM/UF do produto na semântica ComexStat, não município físico.
    """
    return {
        "flow": "export",
        "monthDetail": bool(month_detail),
        "period": {"from": start, "to": end},
        "filters": [{"filter": "ncm", "values": [12011000, 12019000]}],
        "details": ["ncm", "state"],
        "metrics": ["metricFOB", "metricKG"],
    }
