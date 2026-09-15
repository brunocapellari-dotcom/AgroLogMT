from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from collector.official_lineup_html import fetch_official_html, parse_official_lineup_html
from collector.official_lineup_pdf import (
    PDF_ALLOWED_HOSTS,
    discover_paranagua_landing_pages,
    discover_pdf_link_from_landing,
    extract_pdf_tables,
    parse_itaqui_tables,
    parse_paranagua_tables,
)
from collector.shipping_lineup_worker import DEFAULT_CONFIG, load_source_config


TIME_ZONE = ZoneInfo("America/Sao_Paulo")
MAX_HTML_BYTES = 8 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
ITAQUI_STRUCTURAL_SMOKE_URL = (
    "https://www.portodoitaqui.com/public/_files/arquivos/"
    "MAPA%20DE%20ATRACA%C3%87%C3%83O%20-%2006%2003%202026%20-15h00%20-%20clientes_69ab39b275b94.pdf"
)
ITAQUI_STRUCTURAL_REFERENCE = datetime(2026, 3, 6, tzinfo=TIME_ZONE).date()


def _same_host_https(url: str, allowed_hosts: set[str] | frozenset[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
        raise ValueError(f"URL fora da allowlist: {url}")
    if parsed.username or parsed.password:
        raise ValueError("credencial embutida em URL é proibida")


def _get(url: str, *, allowed_hosts: set[str] | frozenset[str], max_bytes: int, accept: str) -> requests.Response:
    _same_host_https(url, allowed_hosts)
    response = requests.get(
        url,
        headers={
            "User-Agent": "AgroLogMT/1.0 (+maritime-lineup-live-probe)",
            "Accept": accept,
        },
        timeout=(10, 40),
        allow_redirects=False,
        stream=True,
    )
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} em {url}")
    _same_host_https(str(response.url), allowed_hosts)
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > max_bytes:
                raise RuntimeError(f"payload declarado excede {max_bytes} bytes: {url}")
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError(f"payload excede {max_bytes} bytes: {url}")
        chunks.append(chunk)
    response._content = b"".join(chunks)
    response._content_consumed = True
    return response


def _probe_html_source(source: dict[str, Any]) -> dict[str, Any]:
    fetched = fetch_official_html(str(source["url"]))
    rows = parse_official_lineup_html(fetched.text, str(source["parser_mode"]))
    if not rows:
        raise RuntimeError(f"{source['source_id']}: página oficial respondeu, mas parser retornou 0 linhas")
    return {
        "source_id": source["source_id"],
        "port_id": source["port_id"],
        "mode": source["parser_mode"],
        "status": "PASS",
        "rows": len(rows),
        "url": fetched.url,
    }


def _fetch_paranagua_index(url: str) -> str:
    response = _get(
        url,
        allowed_hosts={"www.portosdoparana.pr.gov.br", "portosdoparana.pr.gov.br"},
        max_bytes=MAX_HTML_BYTES,
        accept="text/html,application/xhtml+xml",
    )
    content_type = response.headers.get("Content-Type", "")
    if content_type and "html" not in content_type.lower():
        raise RuntimeError(f"índice Paranaguá não HTML: {content_type}")
    return response.text


def _probe_paranagua(source: dict[str, Any]) -> list[dict[str, Any]]:
    index_urls = [str(source["url"]), *[str(item) for item in source.get("additional_index_urls", [])]]
    discovered: dict[str, str] = {}
    for index_url in index_urls:
        discovered.update(discover_paranagua_landing_pages(_fetch_paranagua_index(index_url), index_url))

    required_series = [str(item) for item in source.get("target_series", [])]
    missing = sorted(set(required_series) - set(discovered))
    if missing:
        raise RuntimeError(f"Paranaguá: séries oficiais não descobertas: {missing}")

    today = datetime.now(TIME_ZONE).date()
    results: list[dict[str, Any]] = []
    for series in required_series:
        landing_url = discovered[series]
        landing = _get(
            landing_url,
            allowed_hosts={"www.portosdoparana.pr.gov.br", "portosdoparana.pr.gov.br"},
            max_bytes=MAX_HTML_BYTES,
            accept="text/html,application/xhtml+xml",
        )
        pdf_url = discover_pdf_link_from_landing(landing.text, landing_url)
        pdf = _get(
            pdf_url,
            allowed_hosts=PDF_ALLOWED_HOSTS,
            max_bytes=MAX_PDF_BYTES,
            accept="application/pdf",
        )
        if not pdf.content.startswith(b"%PDF"):
            raise RuntimeError(f"Paranaguá {series}: payload oficial não é PDF")
        tables = extract_pdf_tables(pdf.content)
        rows = parse_paranagua_tables(tables, reference_date=today, series=series)
        if not rows:
            raise RuntimeError(f"Paranaguá {series}: PDF oficial atual retornou 0 linhas programadas")
        results.append({
            "source_id": source["source_id"],
            "port_id": source["port_id"],
            "series": series,
            "status": "PASS",
            "tables": len(tables),
            "rows": len(rows),
            "landing_url": landing_url,
            "pdf_url": pdf_url,
        })
    return results


def _probe_itaqui_structure() -> dict[str, Any]:
    """Validate parser against an official known PDF, without claiming current freshness."""
    pdf = _get(
        ITAQUI_STRUCTURAL_SMOKE_URL,
        allowed_hosts=PDF_ALLOWED_HOSTS,
        max_bytes=MAX_PDF_BYTES,
        accept="application/pdf",
    )
    if not pdf.content.startswith(b"%PDF"):
        raise RuntimeError("Itaqui structural smoke: payload oficial não é PDF")
    tables = extract_pdf_tables(pdf.content)
    rows = parse_itaqui_tables(tables, reference_date=ITAQUI_STRUCTURAL_REFERENCE)
    if not rows:
        raise RuntimeError("Itaqui structural smoke: parser retornou 0 linhas")
    return {
        "source_id": "emap_itaqui_lineup",
        "port_id": "ITAQUI",
        "status": "STRUCTURAL_PASS",
        "freshness_claim": False,
        "reference_date": ITAQUI_STRUCTURAL_REFERENCE.isoformat(),
        "tables": len(tables),
        "rows": len(rows),
        "pdf_url": ITAQUI_STRUCTURAL_SMOKE_URL,
    }


def run(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_source_config(config_path)
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for source in config["sources"]:
        if not source.get("enabled") or not str(source.get("parser_mode", "")).startswith("HTML_"):
            continue
        try:
            checks.append(_probe_html_source(source))
        except Exception as exc:
            errors.append({
                "scope": str(source.get("source_id") or source.get("port_id") or "HTML_OFFICIAL"),
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            })

    paranagua = next((s for s in config["sources"] if s["port_id"] == "PARANAGUA"), None)
    if paranagua is None:
        errors.append({"scope": "PARANAGUA", "error_type": "ConfigError", "error": "fonte ausente"})
    else:
        try:
            checks.extend(_probe_paranagua(paranagua))
        except Exception as exc:
            errors.append({"scope": "PARANAGUA", "error_type": type(exc).__name__, "error": str(exc)[:1000]})

    try:
        checks.append(_probe_itaqui_structure())
    except Exception as exc:
        errors.append({"scope": "ITAQUI_STRUCTURAL", "error_type": type(exc).__name__, "error": str(exc)[:1000]})

    return {
        "probe": "maritime_official_lineup_live",
        "executed_at": datetime.now(TIME_ZONE).isoformat(),
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "errors": errors,
        "notes": {
            "itaqui": "structural smoke only; no current freshness claim until an official latest-index mechanism is validated",
            "paranagua": "live discovery of current official programming PDFs; ATA DE ATRACACAO is intentionally excluded",
        },
    }


def main() -> int:
    report = run(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
