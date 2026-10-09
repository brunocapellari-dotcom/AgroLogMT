#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.agrolog_360_marts import build_agrolog360_sql_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan AgroLog 360 BigQuery analytical marts")
    parser.add_argument("--project", required=True)
    parser.add_argument("--out-dir", default="outputs/agrolog360-marts")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifest = []
    for index, mart in enumerate(build_agrolog360_sql_bundle(args.project), start=1):
        path = out / f"{index:02d}-{mart.mart_id}.sql"
        path.write_text(mart.sql + "\n", encoding="utf-8")
        manifest.append({"mart_id": mart.mart_id, "target": mart.target, "sql_file": str(path)})

    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps({
        "project": args.project,
        "dataset_policy": "create_on_demand_only_when_source_dependencies_exist",
        "marts": manifest,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": "PASS", "manifest": str(manifest_path), "marts": len(manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
