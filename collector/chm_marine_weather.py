from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import requests

from collector.transport_security import validate_https_url


CHM_HOSTS = frozenset({"www.marinha.mil.br", "marinha.mil.br"})
FORECAST_PAGE = "https://www.marinha.mil.br/chm/dados-do-smm-previsao-oceanografica/previsao-meteoceanografica"
MAX_HTML_BYTES = 4 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024
BRASILIA = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class ChmMarineForecastArtifact:
    source_id: str
    page_url: str
    pdf_url: str
    source_updated_at: str | None
    collected_at: str
    sha256: str
    bytes_count: int
    evidence_class: str = "PROJETADO"
    forecast_horizon_hours: int = 48

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bounded_get(url: str, *, max_bytes: int, accept: str, timeout: tuple[int, int] = (10, 40)) -> tuple[bytes, str, str | None]:
    validate_https_url(url, allowed_hosts=CHM_HOSTS)
    response = requests.get(
        url,
        headers={"User-Agent": "AgroLogMT/1.0 (+CHM marine forecast)", "Accept": accept},
        timeout=timeout,
        allow_redirects=False,
        stream=True,
    )
    if response.status_code != 200:
        raise RuntimeError(f"CHM HTTP {response.status_code}: {url}")
    final_url = str(response.url)
    validate_https_url(final_url, allowed_hosts=CHM_HOSTS)
    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > max_bytes:
        raise RuntimeError("CHM payload excede limite declarado")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError("CHM payload excede limite de segurança")
        chunks.append(chunk)
    return b"".join(chunks), final_url, response.headers.get("Content-Type")


def parse_source_updated_at(html: str) -> str | None:
    text = re.sub(r"<[^>]+>", " ", html)
    text = " ".join(unescape(text).split())
    match = re.search(r"Atualizado\s+em\s+(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{1,2}):(\d{2})", text, flags=re.IGNORECASE)
    if not match:
        return None
    day, month, year, hour, minute = map(int, match.groups())
    return datetime(year, month, day, hour, minute, tzinfo=BRASILIA).isoformat()


def discover_forecast_pdf(html: str, page_url: str = FORECAST_PAGE) -> str:
    validate_https_url(page_url, allowed_hosts=CHM_HOSTS)
    hrefs = re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
    candidates: list[str] = []
    for href in hrefs:
        absolute = urljoin(page_url, unescape(href))
        parsed = urlsplit(absolute)
        if parsed.hostname not in CHM_HOSTS:
            continue
        path = parsed.path.lower()
        label = absolute.lower()
        if path.endswith(".pdf") and ("meteo" in label or "previs" in label or "ocean" in label):
            candidates.append(absolute)
    if not candidates:
        # CHM may publish a generically named PDF; accept a unique same-host PDF only.
        same_host_pdfs = [
            urljoin(page_url, unescape(href))
            for href in hrefs
            if urlsplit(urljoin(page_url, unescape(href))).hostname in CHM_HOSTS
            and urlsplit(urljoin(page_url, unescape(href))).path.lower().endswith(".pdf")
        ]
        if len(same_host_pdfs) == 1:
            candidates = same_host_pdfs
    unique = list(dict.fromkeys(candidates))
    if len(unique) != 1:
        raise RuntimeError(f"CHM forecast PDF discovery ambiguous: {len(unique)} candidates")
    return validate_https_url(unique[0], allowed_hosts=CHM_HOSTS)


def fetch_latest_forecast(*, page_url: str = FORECAST_PAGE) -> tuple[ChmMarineForecastArtifact, bytes]:
    html_bytes, observed_page, content_type = _bounded_get(
        page_url,
        max_bytes=MAX_HTML_BYTES,
        accept="text/html,application/xhtml+xml",
    )
    if content_type and "html" not in content_type.lower():
        raise RuntimeError(f"CHM forecast page content-type inesperado: {content_type}")
    html = html_bytes.decode("utf-8", errors="replace")
    pdf_url = discover_forecast_pdf(html, observed_page)
    pdf_bytes, observed_pdf, pdf_type = _bounded_get(
        pdf_url,
        max_bytes=MAX_PDF_BYTES,
        accept="application/pdf",
    )
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError("CHM forecast artifact não é PDF")
    if pdf_type and "pdf" not in pdf_type.lower() and "octet-stream" not in pdf_type.lower():
        raise RuntimeError(f"CHM forecast PDF content-type inesperado: {pdf_type}")
    collected_at = datetime.now(BRASILIA).isoformat()
    artifact = ChmMarineForecastArtifact(
        source_id="chm_meteocean_forecast",
        page_url=observed_page,
        pdf_url=observed_pdf,
        source_updated_at=parse_source_updated_at(html),
        collected_at=collected_at,
        sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        bytes_count=len(pdf_bytes),
    )
    return artifact, pdf_bytes
