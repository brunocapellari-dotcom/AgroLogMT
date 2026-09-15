#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any

from google.cloud import bigquery


def _one(client: Any, sql: str) -> Any:
    rows = list(client.query(sql).result())
    if not rows:
        raise RuntimeError("validation query returned no rows")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate historical MT beef aggregate against canonical Comex NCM table")
    parser.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--dataset", default=os.environ.get("AGROLOG_TRADE_DATASET", "comercio_exterior"))
    parser.add_argument("--location", default=os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1"))
    args = parser.parse_args()
    if not args.project:
        raise SystemExit("Projeto GCP ausente")

    client = bigquery.Client(project=args.project, location=args.location)
    raw = f"{args.project}.{args.dataset}.comexstat_ncm_export"
    view = f"{args.project}.{args.dataset}.v_pecuaria_mt_beef_exports"

    raw_summary = _one(client, f"""
SELECT
  COUNT(*) rows,
  MIN(co_ano) year_min,
  MAX(co_ano) year_max,
  SUM(kg_liquido) kg_liquido,
  SUM(vl_fob) vl_fob
FROM `{raw}`
WHERE sg_uf_ncm='MT'
  AND co_ano >= 1997
  AND (STARTS_WITH(co_ncm,'0201') OR STARTS_WITH(co_ncm,'0202'))
""")
    view_summary = _one(client, f"""
SELECT
  COUNT(*) rows,
  MIN(co_ano) year_min,
  MAX(co_ano) year_max,
  SUM(kg_liquido) kg_liquido,
  SUM(vl_fob_usd) vl_fob
FROM `{view}`
""")
    bad_scope = _one(client, f"""
SELECT COUNT(*) n
FROM `{view}`
WHERE NOT (STARTS_WITH(co_ncm,'0201') OR STARTS_WITH(co_ncm,'0202'))
   OR segmento_carne NOT IN ('fresca_refrigerada','congelada')
""")["n"]
    by_year = list(client.query(f"""
WITH raw_y AS (
  SELECT co_ano year, SUM(kg_liquido) kg, SUM(vl_fob) fob
  FROM `{raw}`
  WHERE sg_uf_ncm='MT' AND co_ano >= 1997
    AND (STARTS_WITH(co_ncm,'0201') OR STARTS_WITH(co_ncm,'0202'))
  GROUP BY year
), view_y AS (
  SELECT co_ano year, SUM(kg_liquido) kg, SUM(vl_fob_usd) fob
  FROM `{view}` GROUP BY year
)
SELECT
  COALESCE(r.year,v.year) year,
  r.kg raw_kg, v.kg view_kg,
  r.fob raw_fob, v.fob view_fob
FROM raw_y r FULL OUTER JOIN view_y v USING(year)
WHERE ABS(COALESCE(r.kg,0)-COALESCE(v.kg,0)) > 0.001
   OR ABS(COALESCE(r.fob,0)-COALESCE(v.fob,0)) > 0.01
ORDER BY year
""").result())

    if int(raw_summary["rows"] or 0) <= 0:
        raise RuntimeError("canonical Comex beef scope is empty")
    if int(view_summary["rows"] or 0) <= 0:
        raise RuntimeError("livestock historical beef view is empty")
    if int(bad_scope or 0) != 0:
        raise RuntimeError(f"historical beef view contains {bad_scope} out-of-scope rows")
    if by_year:
        raise RuntimeError(f"historical beef annual tie-out failed for {len(by_year)} years")
    if abs(float(raw_summary["kg_liquido"] or 0)-float(view_summary["kg_liquido"] or 0)) > 0.001:
        raise RuntimeError("historical beef total kg tie-out failed")
    if abs(float(raw_summary["vl_fob"] or 0)-float(view_summary["vl_fob"] or 0)) > 0.01:
        raise RuntimeError("historical beef total FOB tie-out failed")

    print(json.dumps({
        "status": "PASS",
        "raw_table": raw,
        "view": view,
        "year_min": int(view_summary["year_min"]),
        "year_max": int(view_summary["year_max"]),
        "kg_liquido": float(view_summary["kg_liquido"]),
        "vl_fob_usd": float(view_summary["vl_fob"]),
        "annual_tie_out": True,
        "scope_guard": True
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
