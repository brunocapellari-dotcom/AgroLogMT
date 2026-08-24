#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from collector.ibge_pam import build_canonical_rows, fetch_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe live IBGE PAM canonical pipeline without cloud writes")
    parser.add_argument("--out", default="ibge_pam_canonical_probe.json")
    args = parser.parse_args()
    payload, source_url = fetch_payload()
    collected = datetime.now(timezone.utc).isoformat()
    rows, stats = build_canonical_rows(payload, source_url=source_url, data_coleta=collected)
    if not rows:
        raise RuntimeError("IBGE PAM canonical probe produced no rows")
    if any(row["point_in_time_feature_eligible"] for row in rows):
        raise RuntimeError("IBGE PAM leakage guard failed: realized target became PIT feature")
    result = {
        "status": "pass",
        "source_url": source_url,
        "data_coleta": collected,
        "stats": stats,
        "sample_first": rows[0],
        "sample_last": rows[-1],
        "cloud_write": false if False else False
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "stats": stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
