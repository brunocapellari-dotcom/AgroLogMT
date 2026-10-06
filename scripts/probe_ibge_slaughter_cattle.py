#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.ibge_slaughter import build_canonical_rows, fetch_payload
from collector.ibge_slaughter_bigquery import HEAD_METRIC, WEIGHT_METRIC


def main() -> int:
    parser = argparse.ArgumentParser(description="Live probe IBGE SIDRA quarterly cattle slaughter for Mato Grosso")
    parser.add_argument("--period", default="202601", help="SIDRA quarter code YYYYQQ")
    parser.add_argument("--out")
    args = parser.parse_args()

    payload, observed_url = fetch_payload(period=args.period, timeout=180)
    rows, stats = build_canonical_rows(payload, source_url=observed_url)
    by_metric = {str(row["metric_id"]): float(row["value"]) for row in rows}

    expected = {HEAD_METRIC, WEIGHT_METRIC}
    if set(by_metric) != expected:
        raise RuntimeError(f"IBGE Abate live metric drift: {sorted(by_metric)}")
    heads = by_metric[HEAD_METRIC]
    weight = by_metric[WEIGHT_METRIC]
    if heads <= 0 or weight <= 0:
        raise RuntimeError(f"IBGE Abate live non-positive values: heads={heads} weight={weight}")
    avg_weight = weight / heads
    if not 100 <= avg_weight <= 500:
        raise RuntimeError(f"IBGE Abate live implausible carcass weight: {avg_weight:.2f} kg/head")
    if any(row["geo_id"] != "MT" for row in rows):
        raise RuntimeError("IBGE Abate live geography drift")

    report = {
        "status": "PASS",
        "period": args.period,
        "observed_url": observed_url,
        "records": len(rows),
        "heads": heads,
        "carcass_weight_kg": weight,
        "avg_carcass_weight_kg_head": avg_weight,
        "stats": stats,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
