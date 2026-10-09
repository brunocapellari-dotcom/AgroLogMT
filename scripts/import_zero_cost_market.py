from __future__ import annotations

import argparse
import json

from collector.zero_cost_market import (
    ALLOWED_USAGE_RIGHTS,
    MarketAuthorization,
    load_market_input,
    persist_market_references,
)
from collector.zero_cost_pipeline import ZeroCostRuntime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import authorized market references into AgroLog ZERO_COST"
    )
    parser.add_argument("--input", required=True, help="CSV, JSON or JSONL file")
    parser.add_argument("--root", default=".agrolog-zero-cost")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--usage-rights", required=True, choices=sorted(ALLOWED_USAGE_RIGHTS))
    parser.add_argument(
        "--authorization-basis",
        required=True,
        help="Licence, permission, internal ownership or public-open basis",
    )
    args = parser.parse_args()

    authorization = MarketAuthorization(
        source_id=args.source_id,
        source_name=args.source_name,
        usage_rights=args.usage_rights,
        authorization_basis=args.authorization_basis,
    )
    records = load_market_input(args.input)
    runtime = ZeroCostRuntime(args.root)
    result = persist_market_references(
        runtime,
        records,
        authorization=authorization,
    )
    runtime.write_runtime_manifest()
    print(json.dumps({
        "status": "PASS",
        "mode": "ZERO_COST",
        "rights_checked": True,
        **result,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
