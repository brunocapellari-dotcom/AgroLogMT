#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.adapters import get_adapter
from collector.cli import load_sources
from collector.mapa_sigsif import FEMALE_METRIC, MALE_METRIC, SOURCE_ID, build_canonical_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Live probe MAPA PGA/SIGSIF cattle slaughter snapshot")
    parser.add_argument("--config", default="collector/config/sources.pecuaria.json")
    parser.add_argument("--out")
    args = parser.parse_args()

    specs = load_sources(Path(args.config))
    matches = [spec for spec in specs if spec.source_id == SOURCE_ID]
    if len(matches) != 1:
        raise RuntimeError(f"SIGSIF source config esperado exatamente uma vez; encontrados={len(matches)}")
    spec = matches[0]
    result = get_adapter(spec.method).fetch(spec)
    rows, stats = build_canonical_rows(result.payload, source_url=result.observed_url)

    metrics = {row["metric_id"] for row in rows}
    if metrics != {MALE_METRIC, FEMALE_METRIC}:
        raise RuntimeError(f"SIGSIF live metric drift: {sorted(metrics)}")
    if stats["total"] <= 0:
        raise RuntimeError("SIGSIF live MT bovine total is not positive")
    if stats["internal_reference_period_available"] is not False:
        raise RuntimeError("SIGSIF live unexpectedly gained an internal period; temporal contract must be reviewed")
    if any(row["point_in_time_feature_eligible"] for row in rows):
        raise RuntimeError("SIGSIF live temporal guard failed")
    if any(row["target_role"] != "current_sif_crosscheck_not_historical_flow" for row in rows):
        raise RuntimeError("SIGSIF live target-role drift")

    report = {
        "status": "PASS",
        "observed_url": result.observed_url,
        "content_type": result.content_type,
        "last_modified": result.last_modified,
        "records": len(rows),
        "stats": stats,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
