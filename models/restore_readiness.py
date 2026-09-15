from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RestoreReadiness:
    drill_id: str
    verified: bool
    blocking_reasons: tuple[str, ...]


def evaluate_restore_drill(payload: dict[str, Any]) -> RestoreReadiness:
    drill_id = str(payload.get("drill_id", "")).strip()
    if not drill_id:
        raise ValueError("drill_id is required")

    blocking: list[str] = []
    if str(payload.get("status", "")).upper() != "PASS":
        blocking.append("status_not_pass")

    finished_at = payload.get("finished_at")
    if not finished_at:
        blocking.append("missing_finished_at")

    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise ValueError("validation must be an object")

    for key in ("object_count", "row_count", "hash_or_checksum"):
        status = str(validation.get(key, "")).upper()
        if status not in {"PASS", "NOT_APPLICABLE"}:
            blocking.append(f"{key}_not_verified")

    if str(validation.get("permissions", "")).upper() != "PASS":
        blocking.append("permissions_not_verified")
    if validation.get("secrets_not_exported") is not True:
        blocking.append("secrets_export_risk")

    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not any(str(item).strip() for item in evidence):
        blocking.append("missing_evidence")

    return RestoreReadiness(
        drill_id=drill_id,
        verified=not blocking,
        blocking_reasons=tuple(blocking),
    )


def assert_restore_verified(payload: dict[str, Any]) -> RestoreReadiness:
    readiness = evaluate_restore_drill(payload)
    if not readiness.verified:
        raise RuntimeError(
            f"restore drill {readiness.drill_id} is not verified: "
            + ", ".join(readiness.blocking_reasons)
        )
    return readiness
