from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from html import unescape
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .comexstat_api import ComexStatApiClient
from .models import SourceSpec


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


def _validated_https_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("collector HTTP exige URL HTTPS absoluta")
    if parsed.username or parsed.password:
        raise ValueError("credenciais embutidas na URL são proibidas")
    return url


def _http_get(url: str, *, headers: dict[str, str] | None = None, timeout: int = 60) -> AcquisitionResult:
    _validated_https_url(url)
    request_headers = {"User-Agent": "AgroLogMT/0.1 (+source-monitor)"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    # nosec B310: scheme/authority are validated immediately above; URLs come from versioned SourceSpec.
    with urlopen(request, timeout=timeout) as response:  # nosec B310
        observed_url = response.geturl()
        _validated_https_url(observed_url)
        return AcquisitionResult(
            payload=response.read(),
            observed_url=observed_url,
            content_type=response.headers.get("Content-Type"),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )


def extract_html_links(html: str, base_url: str) -> list[str]:
    """Extrai hrefs em ordem documental e resolve links relativos."""
    _validated_https_url(base_url)
    links: list[str] = []
    for match in re.finditer(r"href\s*=\s*([\"'])(.*?)\1", html, flags=re.IGNORECASE | re.DOTALL):
        href = unescape(match.group(2)).strip()
        if href and not href.lower().startswith(("javascript:", "mailto:", "tel:")):
            candidate = urljoin(base_url, href)
            try:
                _validated_https_url(candidate)
            except ValueError:
                continue
            links.append(candidate)
    return links


def select_first_matching_link(links: list[str], pattern: str, *, same_host_as: str | None = None) -> str:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    expected_host = urlsplit(same_host_as).hostname if same_host_as else None
    for link in links:
        _validated_https_url(link)
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
        return _http_get(spec.url, headers=spec.options.get("headers", {}), timeout=timeout)


class EnvHeaderHttpAdapter:
    """HTTP deterministico com um header sensivel carregado somente do ambiente."""

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
            },
        )
        return HttpAdapter().fetch(child_spec)


class EnvQueryHttpAdapter:
    """HTTP com um parametro de query carregado do ambiente sem versionar o valor."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        param_name = str(spec.options.get("query_param_name", "")).strip()
        env_var = str(spec.options.get("query_env_var", "")).strip()
        if not param_name or not env_var:
            raise ValueError("http_env_query exige options.query_param_name e options.query_env_var")
        secret = os.environ.get(env_var)
        if not secret:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {env_var}")
        parts = urlsplit(spec.url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query[param_name] = secret
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        timeout = int(spec.options.get("timeout_seconds", 60))
        return _http_get(url, headers=spec.options.get("headers", {}), timeout=timeout)


class JsonApiAdapter:
    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        result = _http_get(spec.url, headers={"Accept": "application/json"})
        json.loads(result.payload.decode("utf-8"))
        return result


class LatestAttachmentAdapter:
    """Seleciona o primeiro anexo que casa com um regex em uma pagina HTML."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        page = _http_get(spec.url, headers={"Accept": "text/html,application/xhtml+xml"})
        html = page.payload.decode("utf-8", errors="replace")
        pattern = str(spec.options.get("attachment_url_regex", ""))
        if not pattern:
            raise ValueError("latest_attachment exige options.attachment_url_regex")
        link = select_first_matching_link(extract_html_links(html, page.observed_url), pattern, same_host_as=page.observed_url)
        return _http_get(link)


class ComexStatApiAdapter:
    """Adapter da API pública Comex Stat com allowlist e contrato de query."""

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        query = spec.options.get("query")
        if not isinstance(query, dict):
            raise ValueError("comexstat_api exige options.query")
        client = ComexStatApiClient(timeout=int(spec.options.get("timeout_seconds", 60)))
        payload = client.query(dict(query))
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return AcquisitionResult(payload=body, observed_url="https://comexstat.mdic.gov.br/pt/api")
