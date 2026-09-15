#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def gcloud_value(args: list[str]) -> str:
    return subprocess.check_output(["gcloud", *args], text=True).strip()


def get_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate livestock routes on AgroLog Gateway")
    ap.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    ap.add_argument("--region", default="southamerica-east1")
    ap.add_argument("--service", default="agrolog-gateway")
    ap.add_argument("--out")
    args = ap.parse_args()
    if not args.project:
        raise SystemExit("Projeto GCP ausente")

    service_url = gcloud_value([
        "run", "services", "describe", args.service,
        "--region", args.region, "--project", args.project,
        "--format=value(status.url)",
    ])
    if not service_url:
        raise SystemExit("URL do Gateway não encontrada")
    token = gcloud_value(["auth", "print-identity-token"])

    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    state = get_json(f"{service_url}/v1/pecuaria/herd/state?limit=3", token)
    state_rows = state.get("data") or []
    add("herd_state_source", state.get("source_id") == "ibge_sidra_ppm_3939", state.get("source_id"))
    add("herd_state_rows", len(state_rows) > 0, {"rows": len(state_rows)})
    add(
        "herd_state_guard",
        all(row.get("historical_pit_guard_preserved") is True for row in state_rows),
        state_rows,
    )

    municipal = get_json(
        f"{service_url}/v1/pecuaria/herd/municipal?{urllib.parse.urlencode({'year_start': 2020, 'limit': 3})}",
        token,
    )
    municipal_rows = municipal.get("data") or []
    add("herd_municipal_rows", len(municipal_rows) > 0, {"rows": len(municipal_rows)})
    add(
        "herd_municipal_temporal_guard",
        all(row.get("point_in_time_feature_eligible") is False for row in municipal_rows),
        municipal_rows,
    )

    exports = get_json(f"{service_url}/v1/pecuaria/exports/beef?limit=3", token)
    export_rows = exports.get("data") or []
    add("beef_export_source", exports.get("source_id") == "mdic_comexstat_beef_mt_export_api", exports.get("source_id"))
    add("beef_export_rows", len(export_rows) > 0, {"rows": len(export_rows)})
    add("beef_export_scope", exports.get("scope") == "carne_bovina_in_natura_0201_0202_sem_miudezas", exports.get("scope"))
    add(
        "beef_export_metrics_positive",
        all(float(row.get("kg_liquido") or 0) >= 0 and float(row.get("valor_fob_usd") or 0) >= 0 for row in export_rows),
        export_rows,
    )

    failed = [item for item in checks if not item["passed"]]
    report = {
        "status": "PASS" if not failed else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service_url": service_url,
        "checks": checks,
        "failures": len(failed),
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as exc:
        print(json.dumps({"status": "FAIL", "http_status": exc.code, "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
