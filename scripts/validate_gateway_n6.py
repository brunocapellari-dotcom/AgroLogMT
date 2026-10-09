#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from collector.transport_security import validate_https_url

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def safe(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} inválido: {value!r}")
    return value


def gcloud_value(args: list[str]) -> str:
    return subprocess.check_output(["gcloud", *args], text=True).strip()


def get_json(url: str, token: str) -> dict[str, Any]:
    validate_https_url(url)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - Cloud Run HTTPS URL validated before/after redirect.
        validate_https_url(response.geturl())
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida AgroLog Gateway contra BigQuery real")
    ap.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    ap.add_argument("--region", default="southamerica-east1")
    ap.add_argument("--service", default="agrolog-gateway")
    ap.add_argument("--dataset", default=os.environ.get("AGROLOG_LOGISTICA_DATASET", "logistica"))
    ap.add_argument("--location", default=os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1"))
    ap.add_argument("--uf", default="MT")
    ap.add_argument("--out")
    args = ap.parse_args()
    if not args.project:
        raise SystemExit("Projeto GCP ausente")

    project = safe(args.project, "project")
    dataset = safe(args.dataset, "dataset")
    service_url = gcloud_value([
        "run", "services", "describe", args.service,
        "--region", args.region, "--project", project,
        "--format=value(status.url)",
    ])
    if not service_url:
        raise SystemExit("URL do Gateway não encontrada")
    token = gcloud_value(["auth", "print-identity-token"])

    checks: list[dict[str, Any]] = []
    def add(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    health = get_json(f"{service_url}/healthz", token)
    add("healthz", health.get("status") == "ok", health)

    query = urllib.parse.urlencode({"uf": args.uf})
    gateway = get_json(f"{service_url}/v1/storage/conab/summary?{query}", token)
    data = gateway.get("data") or {}
    add("gateway_source", gateway.get("source_id") == "conab_armazens_cadastrados", gateway.get("source_id"))
    add("gateway_evidence", gateway.get("evidence_class") == "observado", gateway.get("evidence_class"))

    client = bigquery.Client(project=project, location=args.location)
    params = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("uf", "STRING", args.uf)])
    sql = f"""
        SELECT COUNT(DISTINCT warehouse_id) AS quantidade_armazens,
               SUM(COALESCE(capacidade_estatica_t,0)) AS capacidade_estatica_t
        FROM `{project}.{dataset}.v_armazens_conab_latest`
        WHERE uf=@uf
    """
    rows = list(client.query(sql, job_config=params).result())
    direct = dict(rows[0].items()) if rows else {}
    gateway_count = int(data.get("quantidade_armazens") or 0)
    direct_count = int(direct.get("quantidade_armazens") or 0)
    gateway_capacity = float(data.get("capacidade_estatica_t") or 0)
    direct_capacity = float(direct.get("capacidade_estatica_t") or 0)
    add("count_matches_bigquery", gateway_count == direct_count and direct_count > 0,
        {"gateway": gateway_count, "bigquery": direct_count})
    add("capacity_matches_bigquery", abs(gateway_capacity-direct_capacity) < 0.01,
        {"gateway": gateway_capacity, "bigquery": direct_capacity})

    sample = get_json(f"{service_url}/v1/storage/conab/warehouses?{urllib.parse.urlencode({'uf': args.uf, 'limit': 5})}", token)
    sample_rows = sample.get("data") or []
    add("warehouse_query_returns_rows", len(sample_rows) > 0, {"rows": len(sample_rows)})
    add("warehouse_query_filter_preserved", sample.get("filters", {}).get("uf") == args.uf, sample.get("filters"))

    failed = [item for item in checks if not item["passed"]]
    report = {
        "status": "PASS" if not failed else "FAIL",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service_url": service_url,
        "uf": args.uf,
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
