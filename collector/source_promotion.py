from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REQUIRED_CHECKS = (
    "source",
    "collector",
    "storage",
    "normalization",
    "validation",
    "analysis",
    "knowledge",
    "report_or_alert",
    "tests",
    "freshness",
    "security",
    "lineage",
    "observability",
    "backup_restore",
)

ALLOWED_STATUS = {"PASS", "FAIL", "MISSING", "NOT_APPLICABLE"}


@dataclass(frozen=True)
class PromotionEvaluation:
    source_id: str
    target_state: str
    ready: bool
    blocking_checks: tuple[str, ...]
    warnings: tuple[str, ...]


def _validate_check(name: str, payload: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
    status = str(payload.get("status", "MISSING")).upper()
    if status not in ALLOWED_STATUS:
        raise ValueError(f"invalid promotion status for {name}: {status}")
    evidence_raw = payload.get("evidence", [])
    if not isinstance(evidence_raw, list):
        raise ValueError(f"promotion evidence for {name} must be a list")
    evidence = tuple(str(item).strip() for item in evidence_raw if str(item).strip())
    rationale = str(payload.get("rationale", "")).strip()

    if status == "PASS" and not evidence:
        raise ValueError(f"PASS requires evidence for {name}")
    if status == "NOT_APPLICABLE" and not rationale:
        raise ValueError(f"NOT_APPLICABLE requires rationale for {name}")
    return status, evidence, rationale


def evaluate_source_promotion(payload: dict[str, Any]) -> PromotionEvaluation:
    """Evaluate whether a source/module can be promoted without subjective shortcuts.

    PRODUCTION requires every canonical check to be PASS. NOT_APPLICABLE is
    accepted for GATED/SHADOW planning when justified, but it blocks PRODUCTION
    because the AgroLog production criterion requires every operational stage to
    exist and be evidenced.
    """
    source_id = str(payload.get("source_id", "")).strip()
    if not source_id:
        raise ValueError("source_id is required")
    target_state = str(payload.get("target_state", "")).upper()
    if target_state not in {"GATED", "SHADOW", "PRODUCTION"}:
        raise ValueError(f"invalid target_state: {target_state}")

    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("checks must be an object")

    missing_keys = [name for name in REQUIRED_CHECKS if name not in checks]
    if missing_keys:
        raise ValueError(f"missing promotion checks: {', '.join(missing_keys)}")

    blocking: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED_CHECKS:
        status, _, rationale = _validate_check(name, checks[name])
        if status in {"FAIL", "MISSING"}:
            blocking.append(name)
        elif status == "NOT_APPLICABLE":
            if target_state == "PRODUCTION":
                blocking.append(name)
            else:
                warnings.append(f"{name}:NOT_APPLICABLE:{rationale}")

    return PromotionEvaluation(
        source_id=source_id,
        target_state=target_state,
        ready=not blocking,
        blocking_checks=tuple(blocking),
        warnings=tuple(warnings),
    )


def assert_source_promotable(payload: dict[str, Any]) -> PromotionEvaluation:
    evaluation = evaluate_source_promotion(payload)
    if not evaluation.ready:
        raise RuntimeError(
            f"source {evaluation.source_id} is not promotable to {evaluation.target_state}; "
            f"blocking checks: {', '.join(evaluation.blocking_checks)}"
        )
    return evaluation
