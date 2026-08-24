#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from collector.conab_safra_history import discover_archive_by_pattern, discover_publications
from scripts.backfill_conab_safra import build_plan, merge_publications


def summarize(plan: list[dict[str, object]]) -> dict[str, object]:
    by_safra: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "ready": 0, "blocked": 0})
    basis: Counter[str] = Counter()
    for item in plan:
        safra = str(item.get("safra") or "unknown")
        by_safra[safra]["total"] += 1
        if item.get("execution_status") == "ready":
            by_safra[safra]["ready"] += 1
            basis[str(item.get("availability_basis") or "unknown")] += 1
        else:
            by_safra[safra]["blocked"] += 1
    return {
        "total": len(plan),
        "ready": sum(item.get("execution_status") == "ready" for item in plan),
        "blocked_missing_publication_time": sum(item.get("execution_status") == "blocked_missing_original_publication_time" for item in plan),
        "blocked_suspected_site_migration": sum(item.get("execution_status") == "blocked_suspected_site_migration_timestamp" for item in plan),
        "blocked_missing_evidence_basis": sum(item.get("execution_status") == "blocked_missing_availability_evidence_basis" for item in plan),
        "ready_by_availability_basis": dict(sorted(basis.items())),
        "by_safra": dict(sorted(by_safra.items(), reverse=True)),
    }


def _season_start_year(item: dict[str, object]) -> int | None:
    safra = str(item.get("safra") or "")
    if len(safra) < 4 or not safra[:4].isdigit():
        return None
    return int(safra[:4])


def filter_range(plan: list[dict[str, object]], start_year: int, end_year: int) -> list[dict[str, object]]:
    return [item for item in plan if (year := _season_start_year(item)) is not None and start_year <= year <= end_year]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventário read-only do histórico CONAB Safra")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--out", default="conab_history_inventory.json")
    parser.add_argument("--strict-network", action="store_true")
    parser.add_argument("--allow-empty", action="store_true", help="retorna sucesso mesmo quando o intervalo não tem vintages recuperáveis")
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("--start-year deve ser <= --end-year")

    listing = discover_publications()
    archive = discover_archive_by_pattern(
        start_year=args.start_year,
        end_year=args.end_year,
        timeout_errors_are_fatal=args.strict_network,
    )
    publications = merge_publications(listing, archive)
    plan = filter_range(build_plan(publications), args.start_year, args.end_year)
    report = {
        "range": {"start_year": args.start_year, "end_year": args.end_year},
        "policy": {
            "publication_timestamp": "official page or canonical nested page timestamp must be plausible for crop season",
            "site_migration_timestamp": "blocked unless an official nested/original timestamp is independently recovered",
            "raw_download": False,
            "bigquery_write": False,
            "range_pure": True,
        },
        "summary": summarize(plan),
        "items": plan,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    ready = int(report["summary"]["ready"])
    return 0 if ready or args.allow_empty else 2


if __name__ == "__main__":
    raise SystemExit(main())
