#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.first_backtests import balance_identity_backtest, export30_backtest, yield_backtest


def _load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    if data.get("point_in_time_ready") is not True:
        raise RuntimeError("backtest blocked: input is not explicitly point_in_time_ready=true")
    if data.get("qa_status") != "pass":
        raise RuntimeError("backtest blocked: qa_status must be pass")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Run first N6 baseline backtests on a QA-approved point-in-time extract")
    ap.add_argument("--model", choices=["yield", "balance", "export30"], required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--seasonal-period", type=int, default=12)
    ap.add_argument("--out", default="n6_backtest_result.json")
    args = ap.parse_args()
    data = _load(args.input)

    if args.model == "yield":
        result = yield_backtest(data["values"])
    elif args.model == "balance":
        result = balance_identity_backtest(data["rows"])
    else:
        result = export30_backtest(data["values"], seasonal_period=args.seasonal_period)

    payload = result.to_dict()
    payload["source_extract"] = data.get("source_extract")
    payload["point_in_time_ready"] = True
    payload["qa_status"] = "pass"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
