#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from google.cloud import bigquery

from models.pecuaria_trade import build_create_view_sql


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/update canonical livestock analytical views")
    parser.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--trade-dataset", default=os.environ.get("AGROLOG_TRADE_DATASET", "comercio_exterior"))
    parser.add_argument("--location", default=os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1"))
    args = parser.parse_args()
    if not args.project:
        raise SystemExit("Projeto GCP ausente")

    client = bigquery.Client(project=args.project, location=args.location)
    sql = build_create_view_sql(
        project_id=args.project,
        dataset_id=args.trade_dataset,
        view_name="v_pecuaria_mt_beef_exports",
        start_year=1997,
    )
    client.query(sql).result()
    view = f"{args.project}.{args.trade_dataset}.v_pecuaria_mt_beef_exports"
    row = list(client.query(f"SELECT COUNT(*) AS rows, MIN(co_ano) AS year_min, MAX(co_ano) AS year_max FROM `{view}`").result())[0]
    if int(row["rows"] or 0) <= 0:
        raise RuntimeError("historical beef view is empty")
    print(json.dumps({
        "status": "PASS",
        "view": view,
        "rows": int(row["rows"]),
        "year_min": int(row["year_min"]),
        "year_max": int(row["year_max"]),
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
