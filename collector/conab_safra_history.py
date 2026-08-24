from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .adapters import extract_html_links, select_first_matching_link

DEFAULT_LISTING = "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/safra-de-graos/boletim-da-safra-de-graos"


@dataclass(frozen=True)
class SafraPublication:
    item_url: str
    attachment_url: str
    safra: str | None
    levantamento: int | None
    data_publicacao: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _get_text(url: str, timeout: int = 60) -> tuple[str, str]:
    req = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+historical-discovery)"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


def _parse_identity(url: str) -> tuple[str | None, int | None]:
    path = urlsplit(url).path
    safra_match = re.search(r"safra-(\d{4})-(\d{2})", path, flags=re.IGNORECASE)
    safra = f"{safra_match.group(1)}/{safra_match.group(2)}" if safra_match else None
    lev_match = re.search(r"/(\d+)[oº]-levantamento", path, flags=re.IGNORECASE)
    levantamento = int(lev_match.group(1)) if lev_match else None
    return safra, levantamento


def _normalize_publication_time(value: str) -> str | None:
    cleaned = unescape(value).strip()
    if not cleaned:
        return None
    candidates = [cleaned, cleaned.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2})[:h](\d{2}))?", cleaned)
    if match:
        day, month, year = map(int, match.group(1, 2, 3))
        hour = int(match.group(4) or 0)
        minute = int(match.group(5) or 0)
        try:
            # GOV.BR publica em horário local; sem timezone explícito, usamos somente
            # a data civil como disponibilidade conservadora no início do dia UTC.
            return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).isoformat()
        except ValueError:
            return None
    return None


def extract_publication_time(html: str) -> str | None:
    """Extrai timestamp publicado pela página; retorna None em vez de inventar data."""
    meta_patterns = [
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|DC\.date\.issued|date|publication_date)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:article:published_time|DC\.date\.issued|date|publication_date)["\']',
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            normalized = _normalize_publication_time(match.group(1))
            if normalized:
                return normalized

    text_patterns = [
        r"Publicado\s+em\s*:?\s*</?[^>]*>?\s*([^<\n]+)",
        r"Publicado\s+em\s*:?\s*(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}[h:]\d{2})?)",
    ]
    for pattern in text_patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            normalized = _normalize_publication_time(re.sub(r"<[^>]+>", " ", match.group(1)))
            if normalized:
                return normalized
    return None


def discover_publications(listing_url: str = DEFAULT_LISTING, *, max_items: int | None = None) -> list[SafraPublication]:
    html, observed = _get_text(listing_url)
    host = urlsplit(observed).hostname
    item_links: list[str] = []
    seen: set[str] = set()
    for link in extract_html_links(html, observed):
        if urlsplit(link).hostname != host:
            continue
        clean = link.split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if not re.search(r"/\d+[oº]-levantamento-safra-\d{4}-\d{2}$", clean, flags=re.IGNORECASE):
            continue
        if clean not in seen:
            seen.add(clean)
            item_links.append(clean)

    def sort_key(url: str) -> tuple[int, int, int]:
        safra, levantamento = _parse_identity(url)
        if safra:
            year, end = safra.split("/")
            return int(year), int(end), levantamento or 0
        return 0, 0, levantamento or 0

    item_links.sort(key=sort_key, reverse=True)
    if max_items is not None:
        item_links = item_links[:max_items]

    publications: list[SafraPublication] = []
    for item_url in item_links:
        item_html, item_observed = _get_text(item_url)
        links = [
            unescape(urljoin(item_observed, link))
            for link in extract_html_links(item_html, item_observed)
            if urlsplit(link).hostname == urlsplit(item_observed).hostname
        ]
        try:
            attachment = select_first_matching_link(
                links,
                r"(?:previsao|previsão).*safra.*\.xlsx(?:/view)?(?:$|[?#])|\.xlsx(?:/view)?(?:$|[?#])",
                same_host_as=item_observed,
            )
        except RuntimeError:
            continue
        if attachment.endswith("/view"):
            attachment = attachment[:-5] + "/@@download/file"
        elif re.search(r"\.xlsx(?:$|[?#])", attachment, flags=re.IGNORECASE):
            attachment = attachment.split("#", 1)[0].split("?", 1)[0].rstrip("/") + "/@@download/file"
        safra, levantamento = _parse_identity(item_url)
        publications.append(SafraPublication(
            item_url=item_url,
            attachment_url=attachment,
            safra=safra,
            levantamento=levantamento,
            data_publicacao=extract_publication_time(item_html),
        ))
    return publications
