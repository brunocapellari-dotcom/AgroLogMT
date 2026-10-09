from __future__ import annotations

import argparse
import json

from collector.zero_cost_freight import load_freight_input, persist_freight_records
from collector.zero_cost_pipeline import ZeroCostRuntime


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import individual announced freight records into AgroLog ZERO_COST"
    )
    parser.add_argument("--input", required=True, help="JSON array/object or JSONL file")
    parser.add_argument("--root", default=".agrolog-zero-cost")
    args = parser.parse_args()

    runtime = ZeroCostRuntime(args.root)
    records = load_freight_input(args.input)
    result = persist_freight_records(runtime, records)
    runtime.write_runtime_manifest()
    print(json.dumps({
        "status": "PASS",
        "mode": "ZERO_COST",
        "commercial_semantics": "FRETES_ANUNCIADOS",
        "municipality_rate_aggregation": False,
        **result,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
