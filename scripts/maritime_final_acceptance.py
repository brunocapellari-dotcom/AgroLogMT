from __future__ import annotations

import argparse
import json
import os
import py_compile
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from models.maritime_final_readiness import GateEvidence, evaluate_final_readiness


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = (
    "collector",
    "gateway",
    "models",
    "scripts",
    "ckan_connector",
    "socrata_connector",
    "cftc_cot",
    "usda_agtransport",
)
JSON_ROOTS = ("contracts", "collector/config")


@dataclass
class CheckResult:
    name: str
    status: str
    command: list[str] | None = None
    detail: str | None = None


class AcceptanceFailure(RuntimeError):
    pass


def _run(name: str, command: Sequence[str], *, cwd: Path = ROOT) -> CheckResult:
    executable = command[0]
    if shutil.which(executable) is None:
        return CheckResult(name=name, status="FAIL", command=list(command), detail=f"executable not found: {executable}")
    proc = subprocess.run(list(command), cwd=cwd, text=True, check=False)
    return CheckResult(
        name=name,
        status="PASS" if proc.returncode == 0 else "FAIL",
        command=list(command),
        detail=None if proc.returncode == 0 else f"exit_code={proc.returncode}",
    )


def _compile_python() -> CheckResult:
    failures: list[str] = []
    count = 0
    for root_name in PYTHON_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in {".venv", "venv", "node_modules", "__pycache__"} for part in path.parts):
                continue
            count += 1
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                failures.append(f"{path.relative_to(ROOT)}: {exc.msg}")
    return CheckResult(
        name="python_compile_all",
        status="PASS" if not failures and count > 0 else "FAIL",
        detail=f"compiled={count}; failures={failures[:20]}",
    )


def _validate_json() -> CheckResult:
    failures: list[str] = []
    count = 0
    for root_name in JSON_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            count += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:  # syntax/encoding contract gate
                failures.append(f"{path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
    return CheckResult(
        name="json_contracts_all",
        status="PASS" if not failures and count > 0 else "FAIL",
        detail=f"validated={count}; failures={failures[:20]}",
    )


def _validate_workflow_yaml() -> CheckResult:
    try:
        import yaml
    except ImportError:
        return CheckResult(name="github_workflow_yaml_all", status="FAIL", detail="PyYAML not installed")
    failures: list[str] = []
    paths = sorted((ROOT / ".github/workflows").glob("*.yml")) + sorted((ROOT / ".github/workflows").glob("*.yaml"))
    for path in paths:
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failures.append(f"{path.name}: {type(exc).__name__}: {exc}")
    return CheckResult(
        name="github_workflow_yaml_all",
        status="PASS" if paths and not failures else "FAIL",
        detail=f"validated={len(paths)}; failures={failures[:20]}",
    )


def _shell_syntax() -> CheckResult:
    paths = sorted((ROOT / "scripts").glob("*.sh"))
    failures: list[str] = []
    if shutil.which("bash") is None:
        return CheckResult(name="shell_syntax_all", status="FAIL", detail="bash not found")
    for path in paths:
        proc = subprocess.run(["bash", "-n", str(path)], cwd=ROOT, check=False)
        if proc.returncode:
            failures.append(path.name)
    return CheckResult(
        name="shell_syntax_all",
        status="PASS" if paths and not failures else "FAIL",
        detail=f"validated={len(paths)}; failures={failures}",
    )


def _load_evidence(path: Path) -> list[GateEvidence]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("gates") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("evidence JSON must be a list or an object with 'gates'")
    return [GateEvidence(**row) for row in rows]


def run(*, static_only: bool, evidence_path: Path | None) -> dict[str, object]:
    results: list[CheckResult] = []

    # One acceptance run covers the whole repository surface consumed by Maritime.
    results.append(_compile_python())
    results.append(_validate_json())
    results.append(_validate_workflow_yaml())
    results.append(_shell_syntax())
    results.append(_run("unit_tests_all", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
    results.append(_run("synthetic_shared_core", [sys.executable, "scripts/run_n6_synthetic_backtest.py"]))
    results.append(_run("repository_security_policy", [sys.executable, "scripts/security_repo_scan.py"]))
    results.append(_run("bandit_full_python_surface", ["bandit", "-q", "-r", *PYTHON_ROOTS, "-ll", "-ii"]))
    results.append(_run("pip_audit_gateway", ["pip-audit", "-r", "requirements-gateway.txt"]))
    results.append(_run("pip_audit_collector", ["pip-audit", "-r", "requirements-collector.txt"]))

    ui_dir = ROOT / "maritime_ui"
    results.append(_run(
        "ui_dependency_resolution",
        ["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=ui_dir,
    ))
    results.append(_run("ui_production_audit", ["npm", "audit", "--omit=dev", "--audit-level=high"], cwd=ui_dir))
    results.append(_run(
        "ui_install_no_lifecycle",
        ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", "--package-lock=false"],
        cwd=ui_dir,
    ))
    results.append(_run("ui_build", ["npm", "run", "build"], cwd=ui_dir))

    # Container build is part of final acceptance because Docker/runtime drift is a
    # production failure even when unit tests pass.
    results.append(_run("collector_container_build", ["docker", "build", "-t", "agrolog-collector:acceptance", "."]))
    results.append(_run("gateway_container_build", ["docker", "build", "-f", "gateway/Dockerfile", "-t", "agrolog-gateway:acceptance", "."]))

    static_failed = [r.name for r in results if r.status != "PASS"]
    output: dict[str, object] = {
        "acceptance": "AGROLOG_MARITIME_FULL_PROJECT",
        "static_status": "PASS" if not static_failed else "FAIL",
        "checks": [asdict(r) for r in results],
        "failed_checks": static_failed,
        "final_status": "BLOCKED",
    }

    if static_failed:
        return output

    if static_only:
        output["final_status"] = "STATIC_ACCEPTANCE_PASS_OPERATIONAL_EVIDENCE_REQUIRED"
        return output

    if evidence_path is None:
        output["failed_checks"] = ["operational_evidence_missing"]
        return output

    readiness = evaluate_final_readiness(_load_evidence(evidence_path))
    output["readiness"] = readiness.to_dict()
    output["final_status"] = readiness.status
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog Maritime all-or-nothing final acceptance")
    parser.add_argument("--static-only", action="store_true", help="Run complete code/security/build suite without claiming production readiness")
    parser.add_argument("--evidence", type=Path, help="Operational gate evidence JSON required for FINAL_READY")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/maritime/final-acceptance.json")
    args = parser.parse_args()

    report = run(static_only=args.static_only, evidence_path=args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["final_status"] in {"FINAL_READY", "STATIC_ACCEPTANCE_PASS_OPERATIONAL_EVIDENCE_REQUIRED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
