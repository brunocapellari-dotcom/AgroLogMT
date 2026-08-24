from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
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

        value = os.environ.get(env_var)
        if not value:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {env_var}")

        parts = urlsplit(spec.url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        query = [(key, item) for key, item in query if key != param_name]
        query.append((param_name, value))
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
        child_spec = SourceSpec(
            source_id=spec.source_id,
            name=spec.name,
            group=spec.group,
            method="http",
            enabled=spec.enabled,
            url=url,
            expected_frequency=spec.expected_frequency,
            file_extension=spec.file_extension,
            evidence_class=spec.evidence_class,
            source_timezone=spec.source_timezone,
            notes=spec.notes,
            options={
                "timeout_seconds": spec.options.get("timeout_seconds", 60),
                "headers": spec.options.get("headers", {}),
            },
        )
        return HttpAdapter().fetch(child_spec)


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
    raise NotImplementedError(
        f"Metodo '{method}' ainda nao implementado. Ordem de fallback aprovada: "
        "HTTP/API/arquivo -> Crawl4AI -> Playwright -> browser-use."
    )
