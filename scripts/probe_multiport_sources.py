#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from collector.port_lifecycle import OFFICIAL_SOURCES
from collector.transport_security import validate_https_url

PORT_TZ = ZoneInfo("America/Sao_Paulo")
_DATE_PATTERNS = (
    re.compile(r"\b(?P<d>0?[1-9]|[12]\d|3[01])/(?P<m>0?[1-9]|1[0-2])/(?P<y>20\d{2})\b"),
    re.compile(r"\b(?P<y>20\d{2})-(?P<m>0?[1-9]|1[0-2])-(?P<d>0?[1-9]|[12]\d|3[01])\b"),
)


def extract_visible_dates(text: str) -> list[date]:
    """Extract explicit calendar dates without treating them as port observations."""
    values: set[date] = set()
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                values.add(date(int(match.group("y")), int(match.group("m")), int(match.group("d"))))
            except ValueError:
                continue
    return sorted(values)


def classify_page_freshness(text: str, *, collected_at: datetime, freshness_days: int = 4) -> dict[str, object]:
    """Classify only page-level recency; never promote to MULTIPORT_VALIDATED.

    Future ETA dates are reported separately and never used as proof that the
    page itself is fresh. The latest date on or before the local collection date
    is the only date used by the page-recency check.
    """
    if freshness_days < 0:
        raise ValueError("freshness_days deve ser >= 0")
    local_day = collected_at.astimezone(PORT_TZ).date()
    dates = extract_visible_dates(text)
    non_future = [value for value in dates if value <= local_day]
    future = [value for value in dates if value > local_day]
    latest = max(non_future) if non_future else None
    cutoff = local_day - timedelta(days=freshness_days)
    recent = latest is not None and latest >= cutoff
    return {
        "latest_visible_non_future_date": latest.isoformat() if latest else None,
        "future_dates_seen": [value.isoformat() for value in future[-10:]],
        "visible_date_count": len(dates),
        "page_freshness_state": "RECENT_VISIBLE_DATE" if recent else "STALE_OR_NO_VISIBLE_DATE",
        "freshness_days": freshness_days,
        "local_collection_date": local_day.isoformat(),
    }


def probe(url: str, *, collected_at: datetime, timeout: int = 25, freshness_days: int = 4) -> dict[str, object]:
    validate_https_url(url)
    req = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+multiport-probe)", "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(req, timeout=timeout) as response:  # nosec B310 - HTTPS validated before request and after redirect.
            validate_https_url(response.geturl())
            sample = response.read(262144)
            text = sample.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
            status = int(response.status)
            availability = "AVAILABLE" if 200 <= status < 400 else "UNAVAILABLE"
            return {
                "ok": 200 <= status < 400,
                "availability_state": availability,
                "status_code": status,
                "observed_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "sample_bytes": len(sample),
                **classify_page_freshness(text, collected_at=collected_at, freshness_days=freshness_days),
            }
    except Exception as exc:
        return {
            "ok": False,
            "availability_state": "UNAVAILABLE",
            "page_freshness_state": "UNKNOWN_UNAVAILABLE",
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
        }


def main() -> int:
    collected_at = datetime.now(timezone.utc)
    results = {
        system: {"source_url": url, **probe(url, collected_at=collected_at)}
        for system, url in OFFICIAL_SOURCES.items()
    }
    available = sorted(system for system, item in results.items() if item.get("ok"))
    recent_pages = sorted(
        system for system, item in results.items() if item.get("page_freshness_state") == "RECENT_VISIBLE_DATE"
    )
    payload = {
        "collected_at": collected_at.isoformat(),
        "purpose": "source_availability_and_page_recency_only",
        "warning": (
            "HTTP availability and visible dates are source-page diagnostics only. "
            "They do not constitute parsed port-call observations and cannot close MULTIPORT_VALIDATED."
        ),
        "available_systems": available,
        "recent_page_systems": recent_pages,
        "validated_observation_systems": [],
        "multiport_gate_status": "PARTIAL_MULTI_PORT",
        "systems": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if len(available) == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
