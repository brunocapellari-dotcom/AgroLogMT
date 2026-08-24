#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Materializa somente marts intermediários previamente aprovados pelo planner N6")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--require-all", action="store_true")
    ap.add_argument("--out", default="soy_mt_intermediate_marts_materialization.json")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    marts = list(plan.get("marts", []))
    ready = [item for item in marts if item.get("ready")]
    blocked = [item for item in marts if not item.get("ready")]
    if args.require_all and blocked:
        payload = {"status": "blocked", "reason": "require_all", "blocked": [x["mart_id"] for x in blocked]}
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    if not args.execute:
        payload = {
            "status": "dry_run",
            "ready": [x["mart_id"] for x in ready],
            "blocked": [x["mart_id"] for x in blocked],
            "sql_count": len(ready),
        }
        Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise SystemExit("google-cloud-bigquery required") from exc

    project = str(plan["project"])
    client = bigquery.Client(project=project)
    client.query(f"CREATE SCHEMA IF NOT EXISTS `{project}.marts_soy_mt` OPTIONS(location='southamerica-east1')").result()
    results = []
    started = datetime.now(timezone.utc)
    for item in ready:
        client.query(str(item["sql"]), location="southamerica-east1").result()
        results.append({"mart_id": item["mart_id"], "target": item["target"], "status": "materialized"})
    payload = {
        "status": "executed",
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "materialized": results,
        "blocked": [x["mart_id"] for x in blocked],
        "note": "views derivadas; tabelas canonicas permanecem fonte de verdade",
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
