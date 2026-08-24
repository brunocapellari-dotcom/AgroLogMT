#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from collector.conab_safra_history import discover_archive_by_pattern, discover_publications
from scripts.backfill_conab_safra import build_plan, merge_publications


def summarize(plan: list[dict[str, object]]) -> dict[str, object]:
    by_safra: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "ready": 0, "blocked": 0})
    for item in plan:
        safra = str(item.get("safra") or "unknown")
        by_safra[safra]["total"] += 1
        if item.get("execution_status") == "ready":
            by_safra[safra]["ready"] += 1
        else:
            by_safra[safra]["blocked"] += 1
    return {
        "total": len(plan),
        "ready": sum(item.get("execution_status") == "ready" for item in plan),
        "blocked_missing_publication_time": sum(item.get("execution_status") == "blocked_missing_original_publication_time" for item in plan),
        "blocked_suspected_site_migration": sum(item.get("execution_status") == "blocked_suspected_site_migration_timestamp" for item in plan),
        "by_safra": dict(sorted(by_safra.items(), reverse=True)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventário read-only do histórico CONAB Safra")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out", default="conab_history_inventory.json")
    parser.add_argument("--strict-network", action="store_true")
    args = parser.parse_args()

    listing = discover_publications()
    archive = discover_archive_by_pattern(
        start_year=args.start_year,
        end_year=args.end_year,
        timeout_errors_are_fatal=args.strict_network,
    )
    publications = merge_publications(listing, archive)
    plan = build_plan(publications)
    report = {
        "range": {"start_year": args.start_year, "end_year": args.end_year},
        "policy": {
            "publication_timestamp": "official_page_timestamp_must_be_plausible_for_crop_season",
            "site_migration_timestamp": "blocked_until_independent_original_availability_evidence",
            "raw_download": False,
            "bigquery_write": False,
        },
        "summary": summarize(plan),
        "items": plan,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["summary"]["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
