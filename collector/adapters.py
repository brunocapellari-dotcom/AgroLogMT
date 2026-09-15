from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ckan_connector.client import CkanClient

from .comexstat_api import ComexStatApiClient
from .input_security import redact_known_secret, sanitize_url_query_parameter
from .models import SourceSpec
from .transport_security import validate_https_url, validate_same_https_host


DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
MAX_REDIRECTS = 5
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "x-goog-api-key",
}


@dataclass
class AcquisitionResult:
    payload: bytes
    observed_url: str
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    # Optional exact machine-native artifact. ``payload`` remains the parse payload
    # consumed by the pipeline; when raw_payload is present the collector hashes and
    # persists these exact source bytes instead.
    raw_payload: bytes | None = None


class Adapter(Protocol):
    def fetch(self, spec: SourceSpec) -> AcquisitionResult: ...


def _allowed_hosts(url: str, options: dict | None = None, *, key: str = "allowed_hosts") -> set[str]:
    parsed = urlsplit(validate_https_url(url))
    hosts = {str(parsed.hostname).lower().rstrip(".")}
    values = (options or {}).get(key, [])
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        raise ValueError(f"{key} deve ser lista/string de hosts")
    for value in values:
        host = str(value).strip().lower().rstrip(".")
        if not host or "://" in host or "/" in host or "@" in host:
            raise ValueError(f"host inválido em {key}: {value!r}")
        hosts.add(host)
    return hosts


def _max_response_bytes(options: dict | None = None) -> int:
    value = int((options or {}).get("max_response_bytes", DEFAULT_MAX_RESPONSE_BYTES))
    if value < 1_024 or value > 512 * 1024 * 1024:
        raise ValueError("max_response_bytes deve estar entre 1 KiB e 512 MiB")
    return value


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Follow only bounded, explicitly allowed HTTPS redirects.

    Cross-host redirects carrying sensitive request headers are rejected even when
    the destination host is allowlisted. This prevents credential exfiltration via
    a compromised/changed source redirect.
    """

    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = {host.lower().rstrip(".") for host in allowed_hosts}
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.redirect_count += 1
        if self.redirect_count > MAX_REDIRECTS:
            raise HTTPError(newurl, code, "redirect limit exceeded", headers, fp)

        validate_https_url(newurl, allowed_hosts=self.allowed_hosts)
        current_host = (urlsplit(req.full_url).hostname or "").lower().rstrip(".")
        next_host = (urlsplit(newurl).hostname or "").lower().rstrip(".")
        if current_host != next_host:
            request_headers = {str(k).lower(): str(v) for k, v in req.header_items()}
            if any(name in request_headers for name in SENSITIVE_HEADER_NAMES):
                raise HTTPError(newurl, code, "cross-host redirect with sensitive headers blocked", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    allowed_hosts: set[str] | None = None,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> AcquisitionResult:
    allowed = set(allowed_hosts or _allowed_hosts(url))
    validate_https_url(url, allowed_hosts=allowed)
    if timeout < 1 or timeout > 600:
        raise ValueError("timeout HTTP deve estar entre 1 e 600 segundos")
    if max_bytes < 1_024 or max_bytes > 512 * 1024 * 1024:
        raise ValueError("limite de payload HTTP inválido")

    request_headers = {"User-Agent": "AgroLogMT/0.1 (+source-monitor)"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    opener = build_opener(_SafeRedirectHandler(allowed))
    with opener.open(request, timeout=timeout) as response:
        observed_url = response.geturl()
        validate_https_url(observed_url, allowed_hosts=allowed)

        length = response.headers.get("Content-Length")
        if length:
            try:
                declared = int(length)
            except (TypeError, ValueError):
                declared = None
            if declared is not None and declared > max_bytes:
                raise ValueError(f"payload HTTP excede limite: {declared}>{max_bytes}")

        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError(f"payload HTTP excede limite de {max_bytes} bytes")
        return AcquisitionResult(
            payload=payload,
            observed_url=observed_url,
            content_type=response.headers.get("Content-Type"),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )


def extract_html_links(html: str, base_url: str) -> list[str]:
    """Extrai hrefs em ordem documental, mantendo apenas HTTPS absoluto válido."""
    validate_https_url(base_url)
    links: list[str] = []
    for match in re.finditer(r"href\s*=\s*([\"'])(.*?)\1", html, flags=re.IGNORECASE | re.DOTALL):
        href = unescape(match.group(2)).strip()
        if not href or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        candidate = urljoin(base_url, href)
        try:
            validate_https_url(candidate)
        except ValueError:
            continue
        links.append(candidate)
    return links


def select_first_matching_link(links: list[str], pattern: str, *, same_host_as: str | None = None) -> str:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    expected_host = urlsplit(validate_https_url(same_host_as)).hostname if same_host_as else None
    for link in links:
        validate_https_url(link)
        if expected_host and urlsplit(link).hostname != expected_host:
            continue
        if regex.search(link):
            return link
    raise RuntimeError(f"Nenhum link compatível com pattern={pattern!r}")


class HttpAdapter:
    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        timeout = int(spec.options.get("timeout_seconds", 60))
        allowed = _allowed_hosts(spec.url, spec.options)
        return _http_get(
            spec.url,
            headers=spec.options.get("headers", {}),
            timeout=timeout,
            allowed_hosts=allowed,
            max_bytes=_max_response_bytes(spec.options),
        )


class EnvHeaderHttpAdapter:
    """HTTP determinístico com um header sensível carregado somente do ambiente."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        header_name = str(spec.options.get("header_name", "")).strip()
        env_var = str(spec.options.get("header_env_var", "")).strip()
        if not header_name or not env_var:
            raise ValueError("http_env_header exige options.header_name e options.header_env_var")

        secret = os.environ.get(env_var)
        if not secret:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {env_var}")

        prefix = str(spec.options.get("header_value_prefix", ""))
        headers = dict(spec.options.get("headers", {}))
        headers[header_name] = f"{prefix}{secret}"
        child_spec = SourceSpec(
            source_id=spec.source_id,
            name=spec.name,
            group=spec.group,
            method="http",
            enabled=spec.enabled,
            url=spec.url,
            expected_frequency=spec.expected_frequency,
            file_extension=spec.file_extension,
            evidence_class=spec.evidence_class,
            source_timezone=spec.source_timezone,
            notes=spec.notes,
            options={
                "timeout_seconds": spec.options.get("timeout_seconds", 60),
                "headers": headers,
                "allowed_hosts": spec.options.get("allowed_hosts", []),
                "max_response_bytes": spec.options.get("max_response_bytes", DEFAULT_MAX_RESPONSE_BYTES),
            },
        )
        try:
            return HttpAdapter().fetch(child_spec)
        except Exception as exc:
            safe = redact_known_secret(str(exc), secret)
            raise RuntimeError(f"HTTP autenticado por header falhou: {safe}") from None


class EnvQueryHttpAdapter:
    """HTTP com parâmetro de query vindo do ambiente, sem persistir/logar seu valor."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        validate_https_url(spec.url)
        param_name = str(spec.options.get("query_param_name", "")).strip()
        env_var = str(spec.options.get("query_env_var", "")).strip()
        if not param_name or not env_var:
            raise ValueError("http_env_query exige options.query_param_name e options.query_env_var")

        value = os.environ.get(env_var)
        if not value:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {env_var}")

        parts = urlsplit(spec.url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        query = [(key, item) for key, item in query if key != param_name]
        query.append((param_name, value))
        request_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        child_spec = SourceSpec(
            source_id=spec.source_id,
            name=spec.name,
            group=spec.group,
            method="http",
            enabled=spec.enabled,
            url=request_url,
            expected_frequency=spec.expected_frequency,
            file_extension=spec.file_extension,
            evidence_class=spec.evidence_class,
            source_timezone=spec.source_timezone,
            notes=spec.notes,
            options={
                "timeout_seconds": spec.options.get("timeout_seconds", 60),
                "headers": spec.options.get("headers", {}),
                "allowed_hosts": spec.options.get("allowed_hosts", []),
                "max_response_bytes": spec.options.get("max_response_bytes", DEFAULT_MAX_RESPONSE_BYTES),
            },
        )
        try:
            result = HttpAdapter().fetch(child_spec)
        except Exception as exc:
            safe = redact_known_secret(str(exc), value)
            raise RuntimeError(f"HTTP autenticado por query falhou: {safe}") from None
        result.observed_url = sanitize_url_query_parameter(result.observed_url, param_name)
        return result


class CkanResourceAdapter:
    """Resolve um recurso CKAN com allowlist e baixa pelo conector canônico endurecido."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        base_url = str(spec.options.get("base_url", "")).rstrip("/")
        dataset_id = str(spec.options.get("dataset_id", "")).strip()
        resource_id = str(spec.options.get("resource_id", "")).strip()
        resource_name = str(spec.options.get("resource_name", "")).strip()
        if not base_url or not dataset_id:
            raise ValueError("CKAN exige options.base_url e options.dataset_id")
        if not resource_id and not resource_name:
            raise ValueError("CKAN exige options.resource_id ou options.resource_name")
        if spec.options.get("headers"):
            raise ValueError("CKAN canônico não aceita headers arbitrários; use adapter autenticado explícito")

        base_allowed = _allowed_hosts(base_url, spec.options)
        validate_https_url(base_url, allowed_hosts=base_allowed)
        timeout = float(spec.options.get("timeout_seconds", 60))
        max_bytes = _max_response_bytes(spec.options)
        client = CkanClient(
            base_url=base_url,
            timeout=timeout,
            max_retries=int(spec.options.get("max_retries", 3)),
            max_download_bytes=max_bytes,
        )
        resources = client.list_resources(dataset_id)
        selected = None
        for resource in resources:
            if resource_id and resource.resource_id == resource_id:
                selected = resource
                break
            if resource_name and resource.name.strip().casefold() == resource_name.casefold():
                selected = resource
                break
        if selected is None:
            raise RuntimeError(f"Recurso CKAN nao encontrado: {resource_id or resource_name}")

        resource_host = (urlsplit(validate_https_url(selected.url)).hostname or "").lower().rstrip(".")
        resource_allowed = set(base_allowed)
        configured = spec.options.get("resource_allowed_hosts", [])
        if isinstance(configured, str):
            configured = [configured]
        if not isinstance(configured, (list, tuple, set)):
            raise ValueError("resource_allowed_hosts deve ser lista/string")
        resource_allowed.update(str(host).strip().lower().rstrip(".") for host in configured if str(host).strip())
        if resource_host not in resource_allowed:
            raise ValueError(
                f"CKAN publicou recurso em host não autorizado: {resource_host}; "
                "adicione-o explicitamente a resource_allowed_hosts após revisão"
            )
        validate_https_url(selected.url, allowed_hosts=resource_allowed)

        with TemporaryDirectory(prefix="agrolog-ckan-") as temp_dir:
            record = client.download_resource(selected, Path(temp_dir))
            payload = record.dest_path.read_bytes()
        if len(payload) != record.size_bytes:
            raise RuntimeError(
                f"CKAN tamanho inconsistente após download: esperado={record.size_bytes} lido={len(payload)}"
            )
        return AcquisitionResult(
            payload=payload,
            raw_payload=payload,
            observed_url=record.url,
            content_type=record.content_type or selected.format or None,
            last_modified=selected.last_modified,
        )


class GovBrLatestAttachmentAdapter:
    """Descobre e baixa anexo oficial sem sair do host GOV.BR original."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        timeout = int(spec.options.get("timeout_seconds", 60))
        item_pattern = str(spec.options.get("item_url_regex", r"/\d+[oº]-levantamento-safra-"))
        attachment_pattern = str(spec.options.get("attachment_url_regex", r"\.xlsx(?:/view)?(?:$|[?#])"))
        headers = spec.options.get("headers", {})
        max_bytes = _max_response_bytes(spec.options)
        allowed = _allowed_hosts(spec.url, spec.options)

        listing = _http_get(spec.url, headers=headers, timeout=timeout, allowed_hosts=allowed, max_bytes=max_bytes)
        listing_html = listing.payload.decode("utf-8", errors="replace")
        item_url = select_first_matching_link(
            extract_html_links(listing_html, listing.observed_url), item_pattern, same_host_as=listing.observed_url
        )
        validate_same_https_host(item_url, listing.observed_url)
        item = _http_get(item_url, headers=headers, timeout=timeout, allowed_hosts=allowed, max_bytes=max_bytes)
        item_html = item.payload.decode("utf-8", errors="replace")
        attachment_url = select_first_matching_link(
            extract_html_links(item_html, item.observed_url), attachment_pattern, same_host_as=item.observed_url
        )
        if attachment_url.endswith("/view"):
            attachment_url = attachment_url[:-5] + "/@@download/file"
        elif re.search(r"\.xlsx(?:$|[?#])", attachment_url, flags=re.IGNORECASE):
            clean = attachment_url.split("#", 1)[0].split("?", 1)[0]
            attachment_url = clean.rstrip("/") + "/@@download/file"
        validate_same_https_host(attachment_url, item.observed_url)
        return _http_get(
            attachment_url,
            headers=headers,
            timeout=timeout,
            allowed_hosts=allowed,
            max_bytes=max_bytes,
        )


class ComexStatApiAdapter:
    """Coleta operacional mensal pelo endpoint oficial da API ComexStat."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        timeout = int(spec.options.get("timeout_seconds", 120))
        module = str(spec.options.get("module", "general")).strip().lower()
        if module not in {"general", "cities"}:
            raise ValueError("comexstat_api options.module deve ser general ou cities")

        client = ComexStatApiClient(timeout=timeout)
        update = client.last_update()
        competence = update.competence
        if not competence:
            raise RuntimeError("ComexStat API não informou a última competência publicada")

        period_mode = str(spec.options.get("period_mode", "latest_complete_month"))
        if period_mode != "latest_complete_month":
            raise ValueError("somente period_mode=latest_complete_month está homologado")

        flow = str(spec.options.get("flow", "export"))
        filters = spec.options.get("filters", [])
        details = spec.options.get("details", [])
        metrics = spec.options.get("metrics", ["metricFOB", "metricKG"])
        if not isinstance(filters, list) or not isinstance(details, list) or not isinstance(metrics, list):
            raise ValueError("comexstat_api filters/details/metrics devem ser listas")

        payload = {
            "flow": flow,
            "monthDetail": bool(spec.options.get("month_detail", True)),
            "period": {"from": competence, "to": competence},
            "filters": filters,
            "details": details,
            "metrics": metrics,
        }
        response = client.query(payload, module=module)
        encoded = json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return AcquisitionResult(
            payload=encoded,
            observed_url=f"{client.base_url}/{module}?language=pt",
            content_type="application/json",
            last_modified=update.updated,
        )


def get_adapter(method: str) -> Adapter:
    normalized = method.strip().lower()
    if normalized in {"http", "http_file", "json_api", "api"}:
        return HttpAdapter()
    if normalized in {"http_env_header", "api_env_header"}:
        return EnvHeaderHttpAdapter()
    if normalized in {"http_env_query", "api_env_query"}:
        return EnvQueryHttpAdapter()
    if normalized in {"ckan", "ckan_resource"}:
        return CkanResourceAdapter()
    if normalized in {"govbr_latest_attachment", "govbr_attachment"}:
        return GovBrLatestAttachmentAdapter()
    if normalized in {"comexstat_api", "mdic_comexstat_api"}:
        return ComexStatApiAdapter()
    if normalized in {"nass_quickstats", "usda_nass_quickstats"}:
        from .nass_quickstats import NassQuickStatsAdapter

        return NassQuickStatsAdapter()
    raise NotImplementedError(
        f"Metodo '{method}' ainda nao implementado. Ordem de fallback aprovada: "
        "HTTP/API/arquivo -> Crawl4AI -> Playwright -> browser-use."
    )
