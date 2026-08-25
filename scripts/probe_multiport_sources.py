#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from collector.port_lifecycle import OFFICIAL_SOURCES


def probe(url: str, timeout: int = 25) -> dict[str, object]:
    req = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+multiport-probe)", "Accept": "text/html,application/xhtml+xml"})
    try:
        with urlopen(req, timeout=timeout) as response:
            sample = response.read(8192)
            return {
                "ok": 200 <= int(response.status) < 400,
                "status_code": int(response.status),
                "observed_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "sample_bytes": len(sample),
            }
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:1000]}


def main() -> int:
    results = {system: {"source_url": url, **probe(url)} for system, url in OFFICIAL_SOURCES.items()}
    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "source_availability_only",
        "warning": "HTTP availability does not imply fresh lineup evidence or MULTIPORT_VALIDATED.",
        "systems": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(item.get("ok") for item in results.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
