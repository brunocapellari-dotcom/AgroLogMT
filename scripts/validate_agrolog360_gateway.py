#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from collector.transport_security import validate_https_url


def gcloud_value(args: list[str]) -> str:
    return subprocess.check_output(["gcloud", *args], text=True).strip()


def get_json(url: str, token: str) -> dict[str, Any]:
    validate_https_url(url)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - validated Cloud Run HTTPS URL.
        validate_https_url(response.geturl())
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AgroLog 360 Gateway marts in real GCP")
    parser.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--region", default="southamerica-east1")
    parser.add_argument("--service", default="agrolog-gateway")
    parser.add_argument("--uf", default="MT")
    parser.add_argument("--out", default="outputs/agrolog360-gateway-validation.json")
    args = parser.parse_args()
    if not args.project:
        raise SystemExit("Projeto GCP ausente")

    service_url = gcloud_value([
        "run", "services", "describe", args.service,
        "--region", args.region, "--project", args.project,
        "--format=value(status.url)",
    ])
    if not service_url:
        raise SystemExit("URL do Gateway ausente")
    token = gcloud_value(["auth", "print-identity-token"])

    checks: list[dict[str, Any]] = []
    health = get_json(f"{service_url}/healthz", token)
    checks.append({"name": "healthz", "passed": health.get("status") == "ok", "detail": health})

    overview = get_json(f"{service_url}/v1/intelligence/overview?uf={args.uf}", token)
    row = overview.get("data") or {}
    checks.append({
        "name": "overview_source",
        "passed": overview.get("source_id") == "marts_agrolog360.overview_current_v1",
        "detail": overview.get("source_id"),
    })
    checks.append({
        "name": "overview_temporal_evidence",
        "passed": bool(row.get("data_coleta")),
        "detail": row.get("data_coleta"),
    })
    checks.append({
        "name": "overview_storage",
        "passed": row.get("capacidade_estatica_t") is not None,
        "detail": row.get("capacidade_estatica_t"),
    })

    failed = [check for check in checks if not check["passed"]]
    report = {
        "status": "PASS" if not failed else "FAIL",
        "project": args.project,
        "service_url": service_url,
        "uf": args.uf,
        "checks": checks,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": "FAIL", "http_status": exc.code, "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
