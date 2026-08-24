from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MartBlockPlan:
    block_id: str
    required: bool
    ready: bool
    selected_tables: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MartPlan:
    mart_id: str
    materialization_allowed: bool
    required_blocks_ready: int
    required_blocks_total: int
    blocks: tuple[MartBlockPlan, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _table_ready(meta: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not meta.get("exists"):
        reasons.append("missing")
    if meta.get("qa_status") != "pass":
        reasons.append("qa_not_pass")
    if not meta.get("point_in_time_ready"):
        reasons.append("point_in_time_not_ready")
    return not reasons, reasons


def build_plan(contract: dict[str, Any], inventory: dict[str, dict[str, Any]]) -> MartPlan:
    block_plans: list[MartBlockPlan] = []
    for block in contract.get("blocks", []):
        block_id = str(block["block_id"])
        required = bool(block.get("required_for_v1"))
        reasons: list[str] = []
        selected: list[str] = []

        for table in block.get("tables_all", []):
            ready, table_reasons = _table_ready(inventory.get(table, {}))
            if ready:
                selected.append(table)
            else:
                reasons.append(f"{table}:" + ",".join(table_reasons))

        alternatives = list(block.get("tables_any", []))
        if alternatives:
            ready_alts = [table for table in alternatives if _table_ready(inventory.get(table, {}))[0]]
            if ready_alts:
                selected.append(ready_alts[0])
            else:
                alt_reason = []
                for table in alternatives:
                    _, table_reasons = _table_ready(inventory.get(table, {}))
                    alt_reason.append(f"{table}({','.join(table_reasons)})")
                reasons.append("no_ready_alternative:" + "|".join(alt_reason))

        block_ready = not reasons
        block_plans.append(MartBlockPlan(block_id, required, block_ready, tuple(selected), tuple(reasons)))

    required_blocks = [item for item in block_plans if item.required]
    ready_count = sum(item.ready for item in required_blocks)
    allowed = bool(required_blocks) and ready_count == len(required_blocks)
    return MartPlan(
        mart_id=str(contract.get("mart_id", "unknown")),
        materialization_allowed=allowed,
        required_blocks_ready=ready_count,
        required_blocks_total=len(required_blocks),
        blocks=tuple(block_plans),
    )


def assert_materialization_allowed(plan: MartPlan) -> None:
    if plan.materialization_allowed:
        return
    failures = [
        f"{block.block_id}: {'; '.join(block.reasons)}"
        for block in plan.blocks if block.required and not block.ready
    ]
    raise RuntimeError("Data Mart bloqueado: " + " || ".join(failures))
