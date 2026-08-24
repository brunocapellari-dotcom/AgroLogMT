#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

BASIS_RANK = {
    "official_page_timestamp": 3,
    "official_nested_page_timestamp": 2,
}


def _rank(item: dict[str, Any]) -> tuple[int, int, str]:
    ready = 1 if item.get("execution_status") == "ready" and item.get("availability_verified") else 0
    basis = BASIS_RANK.get(str(item.get("availability_basis") or ""), 0)
    published = str(item.get("data_publicacao") or "")
    return ready, basis, published


def merge_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    chosen: dict[tuple[str, int], dict[str, Any]] = {}
    ranges = []
    for report in reports:
        if report.get("range"):
            ranges.append(report["range"])
        for item in report.get("items", []):
            safra = str(item.get("safra") or "")
            levantamento = item.get("levantamento")
            if not safra or not isinstance(levantamento, int):
                continue
            key = (safra, levantamento)
            previous = chosen.get(key)
            if previous is None or _rank(item) > _rank(previous):
                chosen[key] = dict(item)

    items = sorted(chosen.values(), key=lambda x: (str(x.get("safra") or ""), int(x.get("levantamento") or 0)), reverse=True)
    by_safra: dict[str, dict[str, Any]] = defaultdict(lambda: {"ready": 0, "blocked": 0, "levantamentos": []})
    basis = Counter()
    for item in items:
        safra = str(item["safra"])
        by_safra[safra]["levantamentos"].append(int(item["levantamento"]))
        if item.get("execution_status") == "ready":
            by_safra[safra]["ready"] += 1
            basis[str(item.get("availability_basis") or "unknown")] += 1
        else:
            by_safra[safra]["blocked"] += 1
    for row in by_safra.values():
        row["levantamentos"] = sorted(set(row["levantamentos"]))

    years = sorted({int(str(item["safra"])[:4]) for item in items if str(item.get("safra") or "")[:4].isdigit()})
    ready = sum(item.get("execution_status") == "ready" for item in items)
    return {
        "registry_version": "1.0",
        "source_id": "conab_safra_graos_xlsx",
        "ranges_merged": ranges,
        "summary": {
            "vintages": len(items),
            "ready": ready,
            "blocked": len(items) - ready,
            "season_start_year_min": min(years) if years else None,
            "season_start_year_max": max(years) if years else None,
            "ready_by_availability_basis": dict(sorted(basis.items())),
            "by_safra": dict(sorted(by_safra.items(), reverse=True)),
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mescla inventários CONAB em registry deduplicado")
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--out", default="conab_vintage_registry.json")
    args = parser.parse_args()
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.inputs]
    registry = merge_reports(reports)
    text = json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
