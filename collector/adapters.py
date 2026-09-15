from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ckan_connector.client import CkanClient

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


def _http_get(url: str, *, headers: dict[str, str] | None = None, timeout: int = 60) -> AcquisitionResult:
    request_headers = {"User-Agent": "AgroLogMT/0.1 (+source-monitor)"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        return AcquisitionResult(
            payload=response.read(),
            observed_url=response.geturl(),
            content_type=response.headers.get("Content-Type"),
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )


def extract_html_links(html: str, base_url: str) -> list[str]:
    """Extrai hrefs em ordem documental e resolve links relativos."""
    links: list[str] = []
    for match in re.finditer(r"href\s*=\s*([\"'])(.*?)\1", html, flags=re.IGNORECASE | re.DOTALL):
        href = unescape(match.group(2)).strip()
        if href and not href.lower().startswith(("javascript:", "mailto:", "tel:")):
            links.append(urljoin(base_url, href))
    return links


def select_first_matching_link(links: list[str], pattern: str, *, same_host_as: str | None = None) -> str:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    expected_host = urlsplit(same_host_as).hostname if same_host_as else None
    for link in links:
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
    """Resolve e baixa um recurso via o conector CKAN canônico do AgroLog.

    Reutiliza retries, limite de tamanho, download atômico e as guardas de URL/
    redirect do ``ckan_connector``. Não mantém uma segunda implementação de CKAN
    dentro do collector.
    """

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
            raise ValueError("CKAN canônico não aceita headers arbitrários; use um adapter autenticado explícito")

        timeout = float(spec.options.get("timeout_seconds", 60))
        max_bytes = int(spec.options.get("max_download_bytes", 500 * 1024 * 1024))
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
    """Descobre o item mais recente em uma listagem GOV.BR e baixa um anexo oficial.

    O adapter é determinístico: segue apenas links no mesmo host da página inicial,
    seleciona o primeiro item que casa com `item_url_regex`, depois o primeiro anexo
    que casa com `attachment_url_regex`. Para arquivos Plone terminados em `/view`,
    converte para `/@@download/file`.
    """

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        if not spec.url:
            raise ValueError(f"Fonte {spec.source_id} sem URL")
        timeout = int(spec.options.get("timeout_seconds", 60))
        item_pattern = str(spec.options.get("item_url_regex", r"/\d+[oº]-levantamento-safra-"))
        attachment_pattern = str(spec.options.get("attachment_url_regex", r"\.xlsx(?:/view)?(?:$|[?#])"))
        headers = spec.options.get("headers", {})

        listing = _http_get(spec.url, headers=headers, timeout=timeout)
        listing_html = listing.payload.decode("utf-8", errors="replace")
        item_url = select_first_matching_link(
            extract_html_links(listing_html, listing.observed_url), item_pattern, same_host_as=listing.observed_url
        )
        item = _http_get(item_url, headers=headers, timeout=timeout)
        item_html = item.payload.decode("utf-8", errors="replace")
        attachment_url = select_first_matching_link(
            extract_html_links(item_html, item.observed_url), attachment_pattern, same_host_as=item.observed_url
        )
        if attachment_url.endswith("/view"):
            attachment_url = attachment_url[:-5] + "/@@download/file"
        elif re.search(r"\.xlsx(?:$|[?#])", attachment_url, flags=re.IGNORECASE):
            clean = attachment_url.split("#", 1)[0].split("?", 1)[0]
            attachment_url = clean.rstrip("/") + "/@@download/file"
        return _http_get(attachment_url, headers=headers, timeout=timeout)


class ComexStatApiAdapter:
    """Coleta operacional mensal pelo endpoint oficial da API ComexStat.

    O período default é obtido de ``/general/dates/updated``; portanto o AgroLog não
    assume que o mês corrente já está completo. A resposta oficial é persistida como
    JSON RAW. CSV aberto permanece fora deste adapter como rota de backfill/reconciliação.
    """

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
    raise NotImplementedError(
        f"Metodo '{method}' ainda nao implementado. Ordem de fallback aprovada: "
        "HTTP/API/arquivo -> Crawl4AI -> Playwright -> browser-use."
    )
