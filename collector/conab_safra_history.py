from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .adapters import extract_html_links, select_first_matching_link

DEFAULT_LISTING = "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/safra-de-graos/boletim-da-safra-de-graos"
GOVBR_PUBLICATION_TZ = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class SafraPublication:
    item_url: str
    attachment_url: str
    safra: str | None
    levantamento: int | None
    data_publicacao: str | None = None
    availability_basis: str | None = None

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
    cleaned = " ".join(unescape(value).split())
    if not cleaned:
        return None
    for candidate in (cleaned, cleaned.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=GOVBR_PUBLICATION_TZ)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2})[:h](\d{2}))?", cleaned)
    if not match:
        return None
    day, month, year = map(int, match.group(1, 2, 3))
    hour = int(match.group(4) or 0)
    minute = int(match.group(5) or 0)
    try:
        parsed = datetime(year, month, day, hour, minute, tzinfo=GOVBR_PUBLICATION_TZ)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _visible_text(html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(text).split())


def extract_publication_time(html: str) -> str | None:
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
    visible = _visible_text(html)
    match = re.search(r"Publicado\s+em\s+(\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}[h:]\d{2})?)", visible, flags=re.IGNORECASE)
    return _normalize_publication_time(match.group(1)) if match else None


def publication_plausible_for_safra(safra: str | None, data_publicacao: str | None) -> bool:
    if not safra or not data_publicacao:
        return False
    match = re.fullmatch(r"(\d{4})/(\d{2})", safra)
    if not match:
        return False
    start_year = int(match.group(1)); end_two = int(match.group(2))
    end_year = (start_year // 100) * 100 + end_two
    if end_year < start_year:
        end_year += 100
    try:
        published = datetime.fromisoformat(data_publicacao.replace("Z", "+00:00"))
    except ValueError:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    lower = datetime(start_year, 9, 1, tzinfo=timezone.utc)
    upper = datetime(end_year, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
    return lower <= published.astimezone(timezone.utc) <= upper


def _nested_canonical_candidates(html: str, observed_url: str) -> list[str]:
    """Find GOV.BR child pages that repeat the levantamento slug and may preserve original metadata."""
    base_path = urlsplit(observed_url).path.rstrip("/")
    slug = base_path.rsplit("/", 1)[-1]
    host = urlsplit(observed_url).hostname
    out: list[str] = []
    seen: set[str] = set()
    explicit = observed_url.rstrip("/") + "/" + slug
    out.append(explicit); seen.add(explicit)
    for link in extract_html_links(html, observed_url):
        absolute = unescape(urljoin(observed_url, link)).split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if urlsplit(absolute).hostname != host:
            continue
        path = urlsplit(absolute).path.rstrip("/")
        segments = [segment for segment in path.split("/") if segment]
        if len(segments) >= 2 and segments[-1] == slug and segments[-2] == slug and absolute not in seen:
            out.append(absolute); seen.add(absolute)
    return out


def _resolve_publication_time(html: str, observed_url: str, safra: str | None) -> tuple[str | None, str | None, str]:
    direct = extract_publication_time(html)
    if publication_plausible_for_safra(safra, direct):
        return direct, "official_page_timestamp", observed_url
    for candidate in _nested_canonical_candidates(html, observed_url):
        try:
            nested_html, nested_observed = _get_text(candidate)
        except (HTTPError, URLError, TimeoutError, OSError):
            continue
        nested = extract_publication_time(nested_html)
        if publication_plausible_for_safra(safra, nested):
            return nested, "official_nested_page_timestamp", nested_observed
    return direct, None, observed_url


def _publication_from_item(item_url: str) -> SafraPublication | None:
    item_html, item_observed = _get_text(item_url)
    links = [unescape(urljoin(item_observed, link)) for link in extract_html_links(item_html, item_observed) if urlsplit(link).hostname in {None, urlsplit(item_observed).hostname}]
    try:
        attachment = select_first_matching_link(
            links,
            r"(?:previsao|previsão).*safra.*\.xlsx(?:/view)?(?:$|[?#])|\.xlsx(?:/view)?(?:$|[?#])",
            same_host_as=item_observed,
        )
    except RuntimeError:
        return None
    if attachment.endswith("/view"):
        attachment = attachment[:-5] + "/@@download/file"
    elif re.search(r"\.xlsx(?:$|[?#])", attachment, flags=re.IGNORECASE):
        attachment = attachment.split("#", 1)[0].split("?", 1)[0].rstrip("/") + "/@@download/file"
    safra, levantamento = _parse_identity(item_observed)
    publication_time, basis, canonical_url = _resolve_publication_time(item_html, item_observed, safra)
    return SafraPublication(
        item_url=canonical_url,
        attachment_url=attachment,
        safra=safra,
        levantamento=levantamento,
        data_publicacao=publication_time,
        availability_basis=basis,
    )


def discover_publications(listing_url: str = DEFAULT_LISTING, *, max_items: int | None = None) -> list[SafraPublication]:
    html, observed = _get_text(listing_url)
    host = urlsplit(observed).hostname
    item_links: list[str] = []
    seen: set[str] = set()
    for link in extract_html_links(html, observed):
        if urlsplit(link).hostname not in {None, host}:
            continue
        clean = urljoin(observed, link).split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if not re.search(r"/\d+[oº]-levantamento-safra-\d{4}-\d{2}$", clean, flags=re.IGNORECASE):
            continue
        if clean not in seen:
            seen.add(clean); item_links.append(clean)

    def sort_key(url: str) -> tuple[int, int, int]:
        safra, levantamento = _parse_identity(url)
        if safra:
            year, end = safra.split("/")
            return int(year), int(end), levantamento or 0
        return 0, 0, levantamento or 0

    item_links.sort(key=sort_key, reverse=True)
    if max_items is not None:
        item_links = item_links[:max_items]
    return [item for item_url in item_links if (item := _publication_from_item(item_url)) is not None]


def discover_archive_by_pattern(*, start_year: int, end_year: int, timeout_errors_are_fatal: bool = False) -> list[SafraPublication]:
    if start_year > end_year:
        raise ValueError("start_year deve ser <= end_year")
    publications: list[SafraPublication] = []
    seen: set[tuple[str | None, int | None]] = set()
    for year in range(end_year, start_year - 1, -1):
        end_two = (year + 1) % 100
        for levantamento in range(12, 0, -1):
            candidate = f"{DEFAULT_LISTING}/{levantamento}o-levantamento-safra-{year}-{end_two:02d}"
            try:
                item = _publication_from_item(candidate)
            except HTTPError as exc:
                if exc.code in {404, 410}:
                    continue
                if timeout_errors_are_fatal:
                    raise
                continue
            except (URLError, TimeoutError, OSError):
                if timeout_errors_are_fatal:
                    raise
                continue
            if item is None:
                continue
            key = (item.safra, item.levantamento)
            if key not in seen:
                seen.add(key); publications.append(item)
    return publications
