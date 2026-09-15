from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .transport_security import validate_https_url

BASE_URL = "https://www.ana.gov.br/hidrowebservice"
ANA_ALLOWED_HOSTS = {"www.ana.gov.br"}
AUTH_PATH = "/EstacoesTelemetricas/OAuth/v1"
INVENTORY_PATH = "/EstacoesTelemetricas/HidroInventarioEstacoes/v1"
TELEMETRY_PATH = "/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"
TOKEN_TTL = timedelta(minutes=13)


@dataclass(frozen=True)
class AnaStation:
    station_code: str
    name: str | None
    uf: str | None
    latitude: float | None
    longitude: float | None
    river: str | None
    basin_code: str | None
    operating: str | None
    station_type: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnaTelemetry:
    station_code: str
    measurement_time: str
    update_time: str | None
    rainfall_mm: float | None
    rainfall_status: int | None
    river_level_cm: float | None
    river_level_status: int | None
    discharge_m3_s: float | None
    discharge_status: int | None
    evidence_class: str = "observado"
    evidence_subtype: str = "ana_telemetered_station"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _first(row: dict[str, Any], *names: str) -> Any:
    lookup = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # A documentação ANA não declara timezone por registro de medição.
        # Manter tratamento técnico explícito até o runtime validar a semântica temporal.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "dados", "content", "retorno", "devolucao", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        if any(str(key).lower() in {"codigoestacao", "codigo_da_estacao", "codestacao"} for key in payload):
            return [payload]
    return []


def parse_stations(payload: Any) -> list[AnaStation]:
    rows: list[AnaStation] = []
    for row in _records(payload):
        code = _first(row, "Codigo", "CodigoEstacao", "CodigoDaEstacao", "CodEstacao", "codigoestacao")
        if code in (None, ""):
            continue
        rows.append(AnaStation(
            station_code=str(code).strip(),
            name=_first(row, "Estacao_Nome", "Nome", "NomeEstacao", "Estacao", "nomeestacao"),
            uf=_first(row, "UF_Estacao", "UF", "SiglaUF", "uf_estacao"),
            latitude=_float(_first(row, "Latitude", "latitude")),
            longitude=_float(_first(row, "Longitude", "longitude")),
            river=_first(row, "Rio_Nome", "NomeRio", "Rio", "rio"),
            basin_code=str(_first(row, "codigobacia", "CodigoBacia", "CodBacia") or "") or None,
            operating=str(_first(row, "Operando", "EmOperacao", "StatusEstacao", "operando") or "") or None,
            station_type=str(_first(row, "Tipo_Estacao", "TipoEstacao", "tipo_estacao") or "") or None,
        ))
    return rows


def parse_telemetry(payload: Any) -> list[AnaTelemetry]:
    rows: list[AnaTelemetry] = []
    for row in _records(payload):
        code = _first(row, "codigoestacao", "CodigoEstacao", "CodigoDaEstacao", "CodEstacao")
        measured = _iso(_first(row, "Data_Hora_Medicao", "DataHoraMedicao", "DataMedicao", "data_hora_medicao"))
        if code in (None, "") or measured is None:
            continue
        rows.append(AnaTelemetry(
            station_code=str(code).strip(),
            measurement_time=measured,
            update_time=_iso(_first(row, "Data_Atualizacao", "DataAtualizacao", "data_atualizacao")),
            rainfall_mm=_float(_first(row, "Chuva_Adotada", "ChuvaAdotada", "chuva_adotada")),
            rainfall_status=_int(_first(row, "Chuva_Adotada_Status", "Status_Chuva_Adotada", "StatusChuvaAdotada", "status_chuva_adotada")),
            river_level_cm=_float(_first(row, "Cota_Adotada", "CotaAdotada", "cota_adotada")),
            river_level_status=_int(_first(row, "Cota_Adotada_Status", "Status_Cota_Adotada", "StatusCotaAdotada", "status_cota_adotada")),
            discharge_m3_s=_float(_first(row, "Vazao_Adotada", "VazaoAdotada", "vazao_adotada")),
            discharge_status=_int(_first(row, "Vazao_Adotada_Status", "Status_Vazao_Adotada", "StatusVazaoAdotada", "status_vazao_adotada")),
        ))
    rows.sort(key=lambda item: (item.station_code, item.measurement_time))
    return rows


class AnaHidroWebServiceClient:
    def __init__(self, *, identifier: str | None = None, password: str | None = None, base_url: str = BASE_URL, timeout: int = 60) -> None:
        self.identifier = identifier or os.environ.get("ANA_HIDRO_IDENTIFICADOR")
        self.password = password or os.environ.get("ANA_HIDRO_SENHA")
        if not self.identifier or not self.password:
            raise RuntimeError("ANA HidroWebService requer ANA_HIDRO_IDENTIFICADOR e ANA_HIDRO_SENHA")
        self.base_url = validate_https_url(base_url.rstrip("/"), allowed_hosts=ANA_ALLOWED_HOSTS)
        self.timeout = timeout
        self._token: str | None = None
        self._token_at: datetime | None = None

    def _json(self, path: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("path ANA inválido")
        url = self.base_url + path
        if params:
            clean = {key: value for key, value in params.items() if value not in (None, "")}
            if clean:
                url += "?" + urlencode(clean)
        validate_https_url(url, allowed_hosts=ANA_ALLOWED_HOSTS)
        request_headers = {"Accept": "application/json", "User-Agent": "AgroLogMT/0.1 (+ANA HidroWebService)"}
        request_headers.update(headers or {})
        req = Request(url, headers=request_headers, method="GET")
        with urlopen(req, timeout=self.timeout) as response:  # nosec B310 - HTTPS and ANA host validated above.
            validate_https_url(response.geturl(), allowed_hosts=ANA_ALLOWED_HOSTS)
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _token_from_payload(payload: Any) -> str:
        candidates: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            candidates.append(payload)
            candidates.extend(_records(payload))
        elif isinstance(payload, list):
            candidates.extend(_records(payload))
        for row in candidates:
            token = _first(row, "tokenautenticacao", "TokenAutenticacao", "access_token", "accesstoken")
            if token:
                return str(token).strip()
        raise RuntimeError("ANA HidroWebService não retornou token de autenticação reconhecível")

    def token(self, *, force_refresh: bool = False) -> str:
        now = datetime.now(timezone.utc)
        if not force_refresh and self._token and self._token_at and now - self._token_at < TOKEN_TTL:
            return self._token
        payload = self._json(AUTH_PATH, headers={"Identificador": self.identifier, "Senha": self.password})
        self._token = self._token_from_payload(payload)
        self._token_at = now
        return self._token

    def authorized_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._json(path, headers={"Authorization": f"Bearer {self.token()}"}, params=params)

    def stations(self, *, station_code: str | None = None, basin_code: str | None = None, uf: str | None = None) -> list[AnaStation]:
        if not any((station_code, basin_code, uf)):
            raise ValueError("ANA inventário exige ao menos estação, bacia ou UF")
        payload = self.authorized_json(INVENTORY_PATH, params={"CodigoDaEstacao": station_code, "CodigoDaBacia": basin_code, "UF": uf})
        return parse_stations(payload)

    def telemetry(self, station_code: str, *, date_filter: str = "DATA_LEITURA", search_range: str = "DIAS_30") -> list[AnaTelemetry]:
        if not station_code.strip():
            raise ValueError("station_code obrigatório")
        payload = self.authorized_json(
            TELEMETRY_PATH,
            params={"CodigoDaEstacao": station_code, "TipoFiltroData": date_filter, "RangeIntervaloDeBusca": search_range},
        )
        return parse_telemetry(payload)
