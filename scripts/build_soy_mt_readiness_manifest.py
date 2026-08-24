#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.datamart_plan import build_plan

DEFAULT_CONTRACT = Path("contracts/soy_mt_datamart_v01.json")
DEFAULT_EVIDENCE = Path("contracts/soy_mt_readiness_evidence_2026-08-24.json")


def _load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _block_table_names(contract: dict, block_id: str) -> list[str]:
    block = next(item for item in contract["blocks"] if item["block_id"] == block_id)
    return list(block.get("tables_all", [])) + list(block.get("tables_any", []))


def build_inventory(contract: dict, evidence: dict) -> dict[str, dict]:
    inventory: dict[str, dict] = {}
    for block_id, state in evidence["blocks"].items():
        for table in _block_table_names(contract, block_id):
            cloud_verified = bool(state.get("cloud_table_verified"))
            inventory[table] = {
                "exists": cloud_verified,
                "qa_status": "pass" if cloud_verified and state.get("local_qa_status") in {"pass", "beta_pass"} else "unverified",
                "point_in_time_ready": cloud_verified and bool(state.get("point_in_time_evidence")),
            }
    return inventory


def build_manifest(contract: dict, evidence: dict) -> dict:
    plan = build_plan(contract, build_inventory(contract, evidence))
    source_ready = sum(bool(state.get("source_ready")) for state in evidence["blocks"].values())
    strict_source_ready = sum(
        bool(state.get("source_ready"))
        and state.get("local_qa_status") == "pass"
        and bool(state.get("point_in_time_evidence"))
        for state in evidence["blocks"].values()
    )
    blockers = []
    for block in contract["blocks"]:
        block_id = block["block_id"]
        state = evidence["blocks"][block_id]
        reasons = []
        if not state.get("source_ready"):
            reasons.append(f"source_state={state.get('source_state')}")
        if state.get("local_qa_status") not in {"pass", "beta_pass"}:
            reasons.append(f"local_qa={state.get('local_qa_status')}")
        if not state.get("point_in_time_evidence"):
            reasons.append("point_in_time_evidence_missing")
        if not state.get("cloud_table_verified"):
            reasons.append("cloud_table_unverified")
        if reasons:
            blockers.append({"block_id": block_id, "reasons": reasons})

    target = evidence["model_targets"]["yield_realized"]
    return {
        "manifest_version": "SOY_MT_READINESS_MANIFEST_V0_1",
        "mart_id": contract["mart_id"],
        "as_of": evidence["as_of"],
        "required_blocks": len(contract["blocks"]),
        "source_ready_blocks": source_ready,
        "strict_pit_source_ready_blocks": strict_source_ready,
        "cloud_materialization_ready_blocks": plan.required_blocks_ready,
        "cloud_materialization_total_blocks": plan.required_blocks_total,
        "materialization_allowed": plan.materialization_allowed,
        "cloud_authenticated": bool(evidence.get("cloud_authenticated")),
        "block_states": evidence["blocks"],
        "blockers": blockers,
        "cloud_plan": plan.to_dict(),
        "yield_realized_target": target,
        "yield_target_ready_for_research": bool(target.get("source_ready") and target.get("local_qa_status") == "pass"),
        "yield_target_cloud_verified": bool(target.get("cloud_table_verified")),
        "decision": (
            "BLOCK_CLOUD_MATERIALIZATION"
            if not plan.materialization_allowed
            else "ALLOW_CLOUD_MATERIALIZATION"
        ),
        "next_critical_sequence": [
            "authenticate_gcp_without_exporting_credentials",
            "load_and_qa_conab_production_and_storage",
            "load_and_qa_imea_market_then_remove_source_lag",
            "restore_comex_over_valid_tls_channel",
            "materialize_climate_with_point_in_time_availability_semantics",
            "load_ibge_pam_realized_yield_target",
            "materialize_and_reconcile_marts_soy_mt_v0_1"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Soja MT V0.1 readiness manifest")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--out", default="soy_mt_readiness_manifest.json")
    args = parser.parse_args()
    manifest = build_manifest(_load(args.contract), _load(args.evidence))
    Path(args.out).write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_ready": f"{manifest['source_ready_blocks']}/{manifest['required_blocks']}",
        "strict_pit_source_ready": f"{manifest['strict_pit_source_ready_blocks']}/{manifest['required_blocks']}",
        "cloud_ready": f"{manifest['cloud_materialization_ready_blocks']}/{manifest['cloud_materialization_total_blocks']}",
        "materialization_allowed": manifest["materialization_allowed"],
        "decision": manifest["decision"]
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
