from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


REQUIRED_RELEASE_STAGES = (
    "repository_integrity",
    "python_compile_all",
    "tests_deterministic_all",
    "tests_live_all",
    "contracts_and_configs",
    "workflow_and_shell_syntax",
    "source_registry",
    "frontend_reproducible_build",
    "containers_build",
    "secret_scan",
    "vulnerability_scan",
    "sbom",
    "runtime_security",
    "data_quality_and_freshness",
    "backup_restore",
    "gcp_preflight",
    "gcp_core_homologation",
    "final_auditor",
)

ALLOWED_STAGE_STATUS = {"PASS", "FAIL", "BLOCKED"}


@dataclass(frozen=True)
class ReleaseStage:
    name: str
    status: str
    evidence: tuple[str, ...]
    details: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReleaseStage":
        name = str(value.get("name") or "").strip()
        status = str(value.get("status") or "").upper().strip()
        evidence = tuple(str(item).strip() for item in value.get("evidence") or () if str(item).strip())
        details = dict(value.get("details") or {})
        if name not in REQUIRED_RELEASE_STAGES:
            raise ValueError(f"unknown release stage: {name or '<empty>'}")
        if status not in ALLOWED_STAGE_STATUS:
            raise ValueError(f"invalid stage status for {name}: {status or '<empty>'}")
        if status == "PASS" and not evidence:
            raise ValueError(f"PASS stage requires evidence: {name}")
        return cls(name=name, status=status, evidence=evidence, details=details)


def evaluate_release(stages: Iterable[ReleaseStage]) -> dict[str, Any]:
    by_name: dict[str, ReleaseStage] = {}
    for stage in stages:
        if stage.name in by_name:
            raise ValueError(f"duplicate release stage: {stage.name}")
        by_name[stage.name] = stage

    missing = [name for name in REQUIRED_RELEASE_STAGES if name not in by_name]
    failed = [name for name, stage in by_name.items() if stage.status == "FAIL"]
    blocked = [name for name, stage in by_name.items() if stage.status == "BLOCKED"]

    if failed:
        status = "FAIL"
    elif missing or blocked:
        status = "BLOCKED"
    else:
        status = "PASS"

    return {
        "status": status,
        "required_stage_count": len(REQUIRED_RELEASE_STAGES),
        "present_stage_count": len(by_name),
        "missing_stages": missing,
        "failed_stages": sorted(failed),
        "blocked_stages": sorted(blocked),
        "release_ready": status == "PASS",
    }


def validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    version = str(payload.get("version") or "")
    if version != "1.0.0":
        raise ValueError(f"unsupported release manifest version: {version or '<empty>'}")
    stages_payload = payload.get("stages")
    if not isinstance(stages_payload, list):
        raise ValueError("release manifest stages must be a list")
    stages = [ReleaseStage.from_dict(item) for item in stages_payload]
    result = evaluate_release(stages)
    declared = str(payload.get("status") or "").upper()
    if declared and declared != result["status"]:
        raise ValueError(f"declared release status {declared} does not match evaluated {result['status']}")
    return result
