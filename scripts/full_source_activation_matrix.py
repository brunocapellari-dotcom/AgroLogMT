#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.source_registry import DataSourceRegistry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the full AgroLog source activation matrix.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", default="outputs/full-source-activation.json")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    registry = DataSourceRegistry.load(repo / "collector/config/data_source_registry.v1.json")
    rows = []

    for entry in sorted(registry.entries.values(), key=lambda item: item.source_id):
        blockers: list[str] = []
        execution_exists = None

        if entry.execution_ref:
            if "#" in entry.execution_ref:
                relative, _ = entry.execution_ref.split("#", 1)
                execution_exists = (repo / relative).exists()
            else:
                execution_exists = (repo / entry.execution_ref).exists()
            if not execution_exists:
                blockers.append("execution_ref_missing")
        else:
            blockers.append("execution_not_implemented")

        if entry.auth in {"api_key", "secret_manager", "adc"}:
            blockers.append(f"auth_required:{entry.auth}")
        if entry.license.startswith("TO_VALIDATE"):
            blockers.append("license_validation_required")
        if not entry.trusted_transport and entry.status == "active":
            blockers.append("trusted_transport_missing")

        ready_for_live_canary = bool(entry.execution_ref and execution_exists) and not any(
            item == "license_validation_required" for item in blockers
        )
        if entry.status == "active":
            target = "OPERATE_AND_MONITOR"
        elif ready_for_live_canary:
            target = "LIVE_CANARY"
        else:
            target = "IMPLEMENT_OR_UNBLOCK"

        rows.append({
            "source_id": entry.source_id,
            "domain": entry.domain,
            "status": entry.status,
            "execution_ref": entry.execution_ref,
            "execution_exists": execution_exists,
            "auth": entry.auth,
            "license": entry.license,
            "trusted_transport": entry.trusted_transport,
            "ready_for_live_canary": ready_for_live_canary,
            "next_action": target,
            "blockers": blockers,
        })

    report = {
        "total": len(rows),
        "active": sum(row["status"] == "active" for row in rows),
        "gated": sum(row["status"] == "gated" for row in rows),
        "planned": sum(row["status"] == "planned" for row in rows),
        "with_execution": sum(bool(row["execution_ref"]) and bool(row["execution_exists"]) for row in rows),
        "ready_for_live_canary": sum(bool(row["ready_for_live_canary"]) and row["status"] != "active" for row in rows),
        "missing_execution": sum("execution_not_implemented" in row["blockers"] for row in rows),
        "license_validation_required": sum("license_validation_required" in row["blockers"] for row in rows),
        "sources": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "total", "active", "gated", "planned", "with_execution",
        "ready_for_live_canary", "missing_execution", "license_validation_required"
    )}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
