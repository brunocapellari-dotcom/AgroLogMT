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


def _latest_raw_cte(raw: str) -> str:
    return f"""
WITH candidate_rows AS (
  SELECT * FROM `{raw}` WHERE co_ano >= 1997
),
latest_snapshot_by_year AS (
  SELECT
    co_ano,
    ARRAY_AGG(snapshot_id ORDER BY data_coleta DESC, snapshot_id DESC LIMIT 1)[OFFSET(0)] AS snapshot_id
  FROM candidate_rows
  GROUP BY co_ano
),
latest_rows AS (
  SELECT r.*
  FROM candidate_rows r
  JOIN latest_snapshot_by_year s
    ON r.co_ano=s.co_ano AND r.snapshot_id=s.snapshot_id
)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate historical MT beef aggregate against latest canonical Comex annual snapshots")
    parser.add_argument("--project", default=os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--dataset", default=os.environ.get("AGROLOG_TRADE_DATASET", "comercio_exterior"))
    parser.add_argument("--location", default=os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1"))
    args = parser.parse_args()
    if not args.project:
        raise SystemExit("Projeto GCP ausente")

    client = bigquery.Client(project=args.project, location=args.location)
    raw = f"{args.project}.{args.dataset}.comexstat_ncm_export"
    view = f"{args.project}.{args.dataset}.v_pecuaria_mt_beef_exports"
    cte = _latest_raw_cte(raw)

    raw_summary = _one(client, cte + """
SELECT
  COUNT(*) rows,
  MIN(co_ano) year_min,
  MAX(co_ano) year_max,
  COUNT(DISTINCT co_ano) years,
  SUM(kg_liquido) kg_liquido,
  SUM(vl_fob) vl_fob
FROM latest_rows
WHERE sg_uf_ncm='MT'
  AND (STARTS_WITH(co_ncm,'0201') OR STARTS_WITH(co_ncm,'0202'))
""")
    view_summary = _one(client, f"""
SELECT
  COUNT(*) rows,
  MIN(co_ano) year_min,
  MAX(co_ano) year_max,
  COUNT(DISTINCT co_ano) years,
  COUNT(DISTINCT source_snapshot_id) source_snapshots,
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
    mixed_snapshots = _one(client, f"""
SELECT COUNT(*) n FROM (
  SELECT co_ano, COUNT(DISTINCT source_snapshot_id) snapshots
  FROM `{view}`
  GROUP BY co_ano
  HAVING snapshots != 1
)
""")["n"]
    by_year = list(client.query(cte + f"""
, raw_y AS (
  SELECT co_ano year, SUM(kg_liquido) kg, SUM(vl_fob) fob
  FROM latest_rows
  WHERE sg_uf_ncm='MT'
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
    if int(mixed_snapshots or 0) != 0:
        raise RuntimeError(f"historical beef view mixes snapshots in {mixed_snapshots} years")
    if int(raw_summary["years"] or 0) != int(view_summary["years"] or 0):
        raise RuntimeError("historical beef year coverage differs from canonical latest snapshots")
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
        "years": int(view_summary["years"]),
        "source_snapshots": int(view_summary["source_snapshots"]),
        "kg_liquido": float(view_summary["kg_liquido"]),
        "vl_fob_usd": float(view_summary["vl_fob"]),
        "latest_snapshot_per_year": True,
        "annual_tie_out": True,
        "scope_guard": True
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
