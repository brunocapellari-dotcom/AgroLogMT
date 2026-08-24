#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import date
from urllib.parse import urlsplit

CURRENT = "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/EXP_2026.csv"
TRANSITIONAL = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm/EXP_2026.csv"
TRANSITION_END = "2026-10-03"


def requests_probe(url: str) -> dict[str, object]:
    import requests
    try:
        with requests.get(url, headers={"Range":"bytes=0-4095", "User-Agent":"AgroLogMT/0.1 (+tls-transition-probe)"}, stream=True, timeout=(20, 40), allow_redirects=True) as response:
            response.raise_for_status()
            chunk = next((item for item in response.iter_content(chunk_size=4096) if item), b"")
            return {"ok": True, "status_code": response.status_code, "observed_url": response.url, "host": urlsplit(response.url).hostname, "sample_bytes": len(chunk), "content_type": response.headers.get("Content-Type")}
    except Exception as exc:
        return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:1000]}


def curl_probe(url: str) -> dict[str, object]:
    command = ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "40", "--range", "0-4095", "--output", "/tmp/comex-sample.bin", "--write-out", "%{http_code} %{url_effective} %{ssl_verify_result}", url]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return {"ok": result.returncode == 0, "returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()[:1000]}


def main() -> int:
    report = {
        "date": date.today().isoformat(),
        "transition_end": TRANSITION_END,
        "policy": "TLS verification remains mandatory; no verify=false or curl -k allowed.",
        "current": {"url": CURRENT, "requests": requests_probe(CURRENT), "curl": curl_probe(CURRENT)},
        "transitional": {"url": TRANSITIONAL, "requests": requests_probe(TRANSITIONAL), "curl": curl_probe(TRANSITIONAL)},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["current"]["requests"]["ok"] or report["transitional"]["requests"]["ok"]:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
