from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import SourceSpec


@dataclass
class AcquisitionResult:
    payload: bytes
    observed_url: str
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None


class Adapter(Protocol):
    def fetch(self, spec: SourceSpec) -> AcquisitionResult: ...


class HttpAdapter:
    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        headers = {"User-Agent": "AgroLogMT/0.1 (+source-monitor)"}
        headers.update(spec.options.get("headers", {}))
        request = Request(spec.url, headers=headers)
        timeout = int(spec.options.get("timeout_seconds", 60))
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            return AcquisitionResult(
                payload=payload,
                observed_url=response.geturl(),
                content_type=response.headers.get("Content-Type"),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )


class CkanResourceAdapter:
    """Resolve um recurso CKAN e baixa o arquivo publicado pela fonte."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        base_url = str(spec.options.get("base_url", "")).rstrip("/")
        dataset_id = spec.options.get("dataset_id")
        resource_id = spec.options.get("resource_id")
        resource_name = spec.options.get("resource_name")
        if not base_url or not dataset_id:
            raise ValueError("CKAN exige options.base_url e options.dataset_id")

        api_url = f"{base_url}/api/3/action/package_show?{urlencode({'id': dataset_id})}"
        request = Request(api_url, headers={"User-Agent": "AgroLogMT/0.1"})
        timeout = int(spec.options.get("timeout_seconds", 60))
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        if not body.get("success"):
            raise RuntimeError(f"CKAN package_show falhou para {dataset_id}")

        resources = body["result"].get("resources", [])
        selected = None
        for resource in resources:
            if resource_id and resource.get("id") == resource_id:
                selected = resource
                break
            if resource_name and str(resource.get("name", "")).strip().lower() == str(resource_name).strip().lower():
                selected = resource
                break
        if selected is None:
            raise RuntimeError(f"Recurso CKAN nao encontrado: {resource_id or resource_name}")

        resource_url = selected.get("url")
        if not resource_url:
            raise RuntimeError("Recurso CKAN sem URL")
        child_spec = SourceSpec(
            source_id=spec.source_id,
            name=spec.name,
            group=spec.group,
            method="http",
            url=resource_url,
            expected_frequency=spec.expected_frequency,
            file_extension=spec.file_extension,
            evidence_class=spec.evidence_class,
            source_timezone=spec.source_timezone,
            notes=spec.notes,
            options={"timeout_seconds": timeout, "headers": spec.options.get("headers", {})},
        )
        result = HttpAdapter().fetch(child_spec)
        result.content_type = result.content_type or selected.get("mimetype") or selected.get("format")
        return result


_ANA_TOKEN_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
_ANA_TOKEN_LOCK = threading.Lock()


def _extract_ana_token(body: Any) -> str:
    candidates: list[Any] = []
    if isinstance(body, dict):
        candidates.append(body)
        items = body.get("items")
        if isinstance(items, dict):
            candidates.append(items)
        elif isinstance(items, list):
            candidates.extend(item for item in items if isinstance(item, dict))

    for candidate in candidates:
        token = candidate.get("tokenautenticacao") or candidate.get("tokenAutenticacao")
        if token:
            return str(token)
    raise RuntimeError("ANA HidroWebService nao retornou token de autenticacao")


class AnaHidroWebAdapter:
    """Coleta a série telemétrica adotada da API oficial HidroWebService/ANA.

    Credenciais nunca pertencem ao SourceSpec nem ao GitHub. O adaptador resolve
    somente os nomes das variáveis de ambiente configuradas no SourceSpec. Em
    produção, essas variáveis devem ser injetadas pelo Secret Manager/Cloud Run.
    """

    DEFAULT_BASE_URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
    DEFAULT_IDENTIFIER_ENV = "ANA_IDENTIFICADOR"
    DEFAULT_PASSWORD_ENV = "ANA_SENHA"
    TOKEN_TTL_SECONDS = 55 * 60

    def _credentials(self, spec: SourceSpec) -> tuple[str, str]:
        identifier_env = str(spec.options.get("identifier_env", self.DEFAULT_IDENTIFIER_ENV))
        password_env = str(spec.options.get("password_env", self.DEFAULT_PASSWORD_ENV))
        identifier = os.environ.get(identifier_env)
        password = os.environ.get(password_env)
        missing = [name for name, value in ((identifier_env, identifier), (password_env, password)) if not value]
        if missing:
            raise RuntimeError(f"Credencial ANA ausente nas variaveis de ambiente: {', '.join(missing)}")
        return str(identifier), str(password)

    @staticmethod
    def _read_json(request: Request, timeout: int) -> tuple[bytes, Any, str | None]:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            try:
                body = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("ANA HidroWebService retornou resposta nao JSON") from exc
            return payload, body, response.headers.get("Content-Type")

    def _token(self, spec: SourceSpec, base_url: str, timeout: int) -> str:
        identifier, password = self._credentials(spec)
        cache_key = (base_url, identifier)
        now = time.monotonic()
        with _ANA_TOKEN_LOCK:
            cached = _ANA_TOKEN_CACHE.get(cache_key)
            if cached and cached[1] > now:
                return cached[0]

            auth_url = f"{base_url}/OAUth/v1"
            request = Request(
                auth_url,
                headers={
                    "User-Agent": "AgroLogMT/0.1 (+ana-hidrowebservice)",
                    "Accept": "application/json",
                    "Identificador": identifier,
                    "Senha": password,
                },
            )
            _, body, _ = self._read_json(request, timeout)
            token = _extract_ana_token(body)
            _ANA_TOKEN_CACHE[cache_key] = (token, now + self.TOKEN_TTL_SECONDS)
            return token

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        station_code = str(spec.options.get("station_code", "")).strip()
        if not station_code:
            raise ValueError(f"Fonte {spec.source_id} sem options.station_code")

        base_url = str(spec.options.get("base_url", self.DEFAULT_BASE_URL)).rstrip("/")
        timeout = int(spec.options.get("timeout_seconds", 60))
        filter_type = str(spec.options.get("filter_type", "DATA_LEITURA"))
        search_range = str(spec.options.get("search_range", "DIAS_30"))
        route = str(spec.options.get("route", "HidroinfoanaSerieTelemetricaAdotada/v1")).lstrip("/")
        query = urlencode(
            {
                "CodigoDaEstacao": station_code,
                "TipoFiltroData": filter_type,
                "RangeIntervaloDeBusca": search_range,
            }
        )
        url = f"{base_url}/{route}?{query}"
        token = self._token(spec, base_url, timeout)
        request = Request(
            url,
            headers={
                "User-Agent": "AgroLogMT/0.1 (+ana-hidrowebservice)",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        payload, _, content_type = self._read_json(request, timeout)
        return AcquisitionResult(
            payload=payload,
            observed_url=url,
            content_type=content_type or "application/json",
        )


def get_adapter(method: str) -> Adapter:
    normalized = method.strip().lower()
    if normalized in {"http", "http_file", "json_api", "api"}:
        return HttpAdapter()
    if normalized in {"ckan", "ckan_resource"}:
        return CkanResourceAdapter()
    if normalized in {"ana_hidroweb", "ana_hidrowebservice", "hidrowebservice"}:
        return AnaHidroWebAdapter()
    raise NotImplementedError(
        f"Metodo '{method}' ainda nao implementado. Ordem de fallback aprovada: "
        "HTTP/API/arquivo -> Crawl4AI -> Playwright -> browser-use."
    )