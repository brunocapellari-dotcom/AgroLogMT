from __future__ import annotations

import hashlib
import json
import re
from defusedxml import ElementTree as ET
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .transport_security import validate_https_url

SOURCE_ID = "usda_wasde"
PUBLICATION_URL = "https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates"
ALLOWED_HOSTS = {"esmis.nal.usda.gov"}
_WASDE_FILE = re.compile(r"/wasde(?P<month>\d{2})(?P<year>\d{2})(?P<version>v\d+)?\.(?P<fmt>xml|xls|txt|pdf)$", re.I)
_RELEASE_PAGE = re.compile(r"/publication/world-agricultural-supply-and-demand-estimates/(?P<date>\d{4}-\d{2}-\d{2})(?:-\d+)?/?$", re.I)


@dataclass(frozen=True)
class WasdeArtifact:
    url: str
    format: str
    year: int
    month: int
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WasdeCell:
    cell_index: int
    path: str
    attributes_json: str
    raw_text: str
    numeric_value: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value)


def discover_artifacts(html: str, *, base_url: str = PUBLICATION_URL) -> list[WasdeArtifact]:
    parser = _LinkParser()
    parser.feed(html)
    found: dict[tuple[int, int, str, str], WasdeArtifact] = {}
    for href in parser.hrefs:
        absolute = urljoin(base_url, href)
        match = _WASDE_FILE.search(urlparse(absolute).path)
        if not match:
            continue
        yy = int(match.group("year"))
        year = 2000 + yy if yy < 80 else 1900 + yy
        month = int(match.group("month"))
        fmt = match.group("fmt").lower()
        version = match.group("version")
        validate_https_url(absolute, allowed_hosts=ALLOWED_HOSTS)
        found[(year, month, version or "", fmt)] = WasdeArtifact(absolute, fmt, year, month, version)
    return sorted(found.values(), key=lambda item: (item.year, item.month, item.version or "", item.format), reverse=True)


def fetch_publication_html(*, url: str = PUBLICATION_URL, timeout: int = 30) -> str:
    validate_https_url(url, allowed_hosts=ALLOWED_HOSTS)
    request = Request(url, headers={"Accept": "text/html", "User-Agent": "AgroLogMT/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - HTTPS + allowlist validated.
        validate_https_url(response.geturl(), allowed_hosts=ALLOWED_HOSTS)
        return response.read().decode("utf-8", errors="replace")



def discover_release_pages(html: str, *, base_url: str = PUBLICATION_URL) -> list[str]:
    parser = _LinkParser()
    parser.feed(html)
    pages: set[str] = set()
    for href in parser.hrefs:
        absolute = urljoin(base_url, href)
        if _RELEASE_PAGE.search(urlparse(absolute).path):
            validate_https_url(absolute, allowed_hosts=ALLOWED_HOSTS)
            pages.add(absolute)
    return sorted(pages)


def discover_listing_pages(html: str, *, base_url: str = PUBLICATION_URL) -> list[str]:
    parser = _LinkParser()
    parser.feed(html)
    base_path = urlparse(PUBLICATION_URL).path.rstrip("/")
    pages: set[str] = set()
    for href in parser.hrefs:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.path.rstrip("/") == base_path and "page=" in parsed.query:
            validate_https_url(absolute, allowed_hosts=ALLOWED_HOSTS)
            pages.add(absolute)
    return sorted(pages)


def publication_date_from_release_url(url: str) -> str | None:
    match = _RELEASE_PAGE.search(urlparse(url).path)
    return match.group("date") if match else None

def fetch_artifact(artifact: WasdeArtifact, *, timeout: int = 60) -> bytes:
    validate_https_url(artifact.url, allowed_hosts=ALLOWED_HOSTS)
    request = Request(artifact.url, headers={"Accept": "*/*", "User-Agent": "AgroLogMT/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - HTTPS + allowlist validated.
        validate_https_url(response.geturl(), allowed_hosts=ALLOWED_HOSTS)
        return response.read()


def _number(text: str) -> float | None:
    cleaned = text.strip().replace(",", "")
    if not cleaned or cleaned in {"--", "NA", "N/A"}:
        return None
    cleaned = cleaned.rstrip("%")
    try:
        return float(cleaned)
    except ValueError:
        return None


def flatten_xml(payload: bytes) -> list[WasdeCell]:
    root = ET.fromstring(payload)
    rows: list[WasdeCell] = []

    def walk(node: ET.Element, path: str, inherited: dict[str, str]) -> None:
        tag = node.tag.split("}", 1)[-1]
        here = f"{path}/{tag}" if path else tag
        context = dict(inherited)
        for key, value in sorted(node.attrib.items()):
            context[f"{tag}.{key}"] = str(value)
        children = list(node)
        text = (node.text or "").strip()
        if not children and (text or node.attrib):
            rows.append(WasdeCell(
                cell_index=len(rows),
                path=here,
                attributes_json=json.dumps(context, ensure_ascii=False, sort_keys=True),
                raw_text=text,
                numeric_value=_number(text),
            ))
        for child in children:
            walk(child, here, context)

    walk(root, "", {})
    if not rows:
        raise ValueError("WASDE XML produced no leaf cells")
    return rows


def artifact_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
