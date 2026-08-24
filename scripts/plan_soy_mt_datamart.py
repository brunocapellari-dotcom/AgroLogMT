#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.datamart_plan import build_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Planeja materialização do Data Mart Soja MT sem fazer escrita")
    parser.add_argument("--readiness", required=True, help="JSON produzido por inspect_n6_bigquery_readiness.py")
    parser.add_argument("--contract", default="contracts/soy_mt_datamart.v1.json")
    parser.add_argument("--out", default="soy_mt_datamart_plan.json")
    args = parser.parse_args()

    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))
    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    inventory = readiness.get("inventory")
    if not isinstance(inventory, dict):
        raise ValueError("readiness sem inventory")
    plan = build_plan(contract, inventory)
    payload = {
        "read_only": True,
        "source_readiness": args.readiness,
        "contract": args.contract,
        "plan": plan.to_dict(),
        "next_action": "materialize" if plan.materialization_allowed else "close_required_block_failures",
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if plan.materialization_allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
