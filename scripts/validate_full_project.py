from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from models.project_release_gate import ReleaseStage, evaluate_release


EXCLUDED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", "outputs"
}
REMOTE_ACTION_RE = re.compile(r"^\s*-\s*uses:\s*([^#\s]+)", re.MULTILINE)
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
LIVE_TEST_RE = re.compile(r"(?:^|[_-])live(?:[_-]|\.py$)", re.IGNORECASE)


def excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def files(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob(pattern)
        if path.is_file() and not excluded(path.relative_to(root))
    )


def stage(name: str, status: str, evidence: Iterable[str] = (), **details: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "evidence": [str(item) for item in evidence if str(item).strip()],
        "details": details,
    }


def command(argv: list[str], *, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
    return proc.returncode, output[-20000:]


def check_python(repo: Path) -> dict[str, Any]:
    candidates = files(repo, "*.py")
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="agrolog-pyc-") as temp:
        base = Path(temp)
        for index, path in enumerate(candidates):
            try:
                py_compile.compile(str(path), cfile=str(base / f"{index}.pyc"), doraise=True)
            except Exception as exc:  # pragma: no cover - failure evidence path
                failures.append(f"{path.relative_to(repo)}: {exc}")
    return stage(
        "python_compile_all",
        "FAIL" if failures else "PASS",
        [] if failures else [f"compiled:{len(candidates)}"],
        python_files=len(candidates),
        failures=failures,
    )


def _test_paths(repo: Path, *, live: bool) -> list[Path]:
    candidates = [path for path in files(repo, "test*.py") if "tests" in path.parts]
    return [path for path in candidates if bool(LIVE_TEST_RE.search(path.name)) == live]


def _junit_counts(report: Path) -> dict[str, int]:
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if not report.is_file():
        return counts
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites and root.tag == "testsuites":
        suites = list(root.iter("testsuite"))
    for suite in suites:
        for key in counts:
            counts[key] += int(suite.attrib.get(key, "0") or 0)
    return counts


def run_tests(repo: Path, *, live: bool) -> dict[str, Any]:
    selected = _test_paths(repo, live=live)
    name = "tests_live_all" if live else "tests_deterministic_all"
    if not selected:
        return stage(name, "BLOCKED" if live else "FAIL", [], blocker="no matching test files")
    if not which("pytest"):
        return stage(name, "BLOCKED", [], blocker="pytest unavailable")

    with tempfile.TemporaryDirectory(prefix="agrolog-pytest-") as temp:
        junit = Path(temp) / "junit.xml"
        argv = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            f"--junitxml={junit}",
            *[str(path.relative_to(repo)) for path in selected],
        ]
        code, output = command(argv, cwd=repo)
        counts = _junit_counts(junit)

    failure_count = counts["failures"] + counts["errors"] + counts["skipped"]
    if code != 0 and failure_count == 0:
        failure_count = 1
    status = "FAIL" if failure_count else "PASS"
    return stage(
        name,
        status,
        [] if failure_count else [
            f"test_files:{len(selected)}",
            f"tests_run:{counts['tests']}",
            "skipped:0",
            "runner:pytest",
        ],
        test_files=len(selected),
        tests_run=counts["tests"],
        skipped=counts["skipped"],
        failures=counts["failures"],
        errors=counts["errors"],
        pytest_exit_code=code,
        output=output,
    )


def check_json_and_yaml(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    json_paths = files(repo, "*.json")
    json_failures: list[str] = []
    for path in json_paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            json_failures.append(f"{path.relative_to(repo)}: {exc}")
    contracts = stage(
        "contracts_and_configs",
        "FAIL" if json_failures else "PASS",
        [] if json_failures else [f"json_valid:{len(json_paths)}"],
        json_files=len(json_paths),
        failures=json_failures,
    )

    workflow_root = repo / ".github" / "workflows"
    yaml_paths = files(workflow_root, "*.yml") + files(workflow_root, "*.yaml")
    yaml_paths += [path for path in files(repo, "cloudbuild.yaml") if path not in yaml_paths]
    yaml_failures: list[str] = []
    try:
        import yaml
    except Exception as exc:
        yaml_failures.append(f"PyYAML unavailable: {exc}")
    else:
        for path in sorted(set(yaml_paths)):
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception as exc:
                yaml_failures.append(f"{path.relative_to(repo)}: {exc}")

    shell_paths = files(repo / "scripts", "*.sh")
    shell_failures: list[str] = []
    if not which("bash"):
        shell_failures.append("bash unavailable")
    else:
        for path in shell_paths:
            code, output = command(["bash", "-n", str(path)], cwd=repo)
            if code:
                shell_failures.append(f"{path.relative_to(repo)}: {output}")

    failures = yaml_failures + shell_failures
    workflows = stage(
        "workflow_and_shell_syntax",
        "FAIL" if failures else "PASS",
        [] if failures else [f"yaml_valid:{len(yaml_paths)}", f"shell_valid:{len(shell_paths)}"],
        workflow_yaml_files=len(yaml_paths),
        shell_files=len(shell_paths),
        failures=failures,
    )
    return contracts, workflows


def check_action_pins(repo: Path) -> list[str]:
    failures: list[str] = []
    root = repo / ".github" / "workflows"
    for path in files(root, "*.yml") + files(root, "*.yaml"):
        text = path.read_text(encoding="utf-8")
        for match in REMOTE_ACTION_RE.finditer(text):
            ref = match.group(1)
            if ref.startswith("./"):
                continue
            if "@" not in ref:
                failures.append(f"{path.relative_to(repo)}: action without ref: {ref}")
                continue
            _, version = ref.rsplit("@", 1)
            if not FULL_SHA_RE.fullmatch(version):
                failures.append(f"{path.relative_to(repo)}: action not pinned by full SHA: {ref}")
    return failures


def check_docker_nonroot(repo: Path) -> list[str]:
    failures: list[str] = []
    for path in files(repo, "Dockerfile"):
        users: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].upper() == "USER":
                users.append(parts[1].strip())
        if not users or users[-1].lower() in {"root", "0", "0:0"}:
            failures.append(f"{path.relative_to(repo)}: final runtime USER is not explicitly non-root")
    return failures


def check_repository_integrity(repo: Path) -> dict[str, Any]:
    failures = check_action_pins(repo) + check_docker_nonroot(repo)
    required = [
        "AGENTS.md",
        "CLAUDE.md",
        "docs/ARCHITECTURE.md",
        "docs/DATA_GOVERNANCE.md",
        "docs/SECURITY.md",
        "docs/FINAL_RELEASE_GATE.md",
        "collector/config/data_source_registry.v1.json",
        "contracts/full_project_release_gate.v1.schema.json",
    ]
    for relative in required:
        if not (repo / relative).is_file():
            failures.append(f"missing required canonical file: {relative}")
    return stage(
        "repository_integrity",
        "FAIL" if failures else "PASS",
        [] if failures else ["canonical_files_present", "actions_sha_pinned", "docker_nonroot"],
        failures=failures,
    )


def check_registry(repo: Path) -> dict[str, Any]:
    failures: list[str] = []
    count = 0
    try:
        from collector.source_registry import DataSourceRegistry

        registry = DataSourceRegistry.load(repo / "collector/config/data_source_registry.v1.json")
        count = len(registry.entries)
        for entry in registry.entries.values():
            ref = entry.execution_ref
            if not ref:
                continue
            file_part = str(ref).split("#", 1)[0].rstrip("/")
            if not (repo / file_part).exists():
                failures.append(f"{entry.source_id}: missing execution_ref target {file_part}")
    except Exception as exc:
        failures.append(str(exc))
    return stage(
        "source_registry",
        "FAIL" if failures else "PASS",
        [] if failures else [f"registry_sources:{count}"],
        registered_sources=count,
        failures=failures,
    )


def check_frontend(repo: Path) -> dict[str, Any]:
    package_json = repo / "maritime_ui" / "package.json"
    lock = repo / "maritime_ui" / "package-lock.json"
    failures: list[str] = []
    if not package_json.is_file():
        failures.append("maritime_ui/package.json missing")
    if not lock.is_file():
        failures.append("maritime_ui/package-lock.json missing: reproducible build is not proven")
    if failures:
        return stage("frontend_reproducible_build", "FAIL", [], failures=failures)
    if not which("npm"):
        return stage("frontend_reproducible_build", "BLOCKED", [], blocker="npm unavailable")

    code, install_output = command(
        ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=repo / "maritime_ui",
    )
    if code:
        return stage("frontend_reproducible_build", "FAIL", [], step="npm_ci", output=install_output)
    code, build_output = command(["npm", "run", "build"], cwd=repo / "maritime_ui")
    return stage(
        "frontend_reproducible_build",
        "PASS" if code == 0 else "FAIL",
        ["npm_ci", "npm_run_build"] if code == 0 else [],
        output=build_output,
    )


def external_stage(name: str, env_name: str, *, exact_line: str | None = None) -> dict[str, Any]:
    value = os.environ.get(env_name, "").strip()
    if not value:
        return stage(name, "BLOCKED", [], blocker=f"missing {env_name}")
    path = Path(value)
    if not path.is_file():
        return stage(name, "FAIL", [], error=f"evidence file does not exist: {value}")
    if path.stat().st_size <= 0:
        return stage(name, "FAIL", [], error=f"evidence file is empty: {value}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return stage(name, "FAIL", [], error=f"evidence file contains no usable content: {value}")
    if exact_line and exact_line not in {line.strip() for line in text.splitlines()}:
        return stage(name, "FAIL", [], error=f"required evidence line missing: {exact_line}")
    return stage(name, "PASS", [str(path)], bytes=path.stat().st_size)


def build_report(repo: Path, *, mode: str) -> dict[str, Any]:
    contracts_stage, workflow_stage = check_json_and_yaml(repo)
    stages = [
        check_repository_integrity(repo),
        check_python(repo),
        run_tests(repo, live=False),
        run_tests(repo, live=True) if mode == "final" else stage(
            "tests_live_all", "BLOCKED", [], blocker="final mode required"
        ),
        contracts_stage,
        workflow_stage,
        check_registry(repo),
        check_frontend(repo),
        external_stage("containers_build", "AGROLOG_EVIDENCE_CONTAINERS"),
        external_stage("secret_scan", "AGROLOG_EVIDENCE_GITLEAKS"),
        external_stage("vulnerability_scan", "AGROLOG_EVIDENCE_TRIVY"),
        external_stage("sbom", "AGROLOG_EVIDENCE_SBOM"),
        external_stage("runtime_security", "AGROLOG_EVIDENCE_RUNTIME_SECURITY"),
        external_stage("data_quality_and_freshness", "AGROLOG_EVIDENCE_DATA_QUALITY"),
        external_stage("backup_restore", "AGROLOG_EVIDENCE_RESTORE"),
        external_stage("gcp_preflight", "AGROLOG_EVIDENCE_GCP_PREFLIGHT"),
        external_stage(
            "gcp_core_homologation",
            "AGROLOG_EVIDENCE_N6_CORE",
            exact_line="N6 CORE HOMOLOGATION: PASS",
        ),
        external_stage("final_auditor", "AGROLOG_EVIDENCE_FINAL_AUDITOR"),
    ]
    evaluation = evaluate_release([ReleaseStage.from_dict(item) for item in stages])
    blockers = [
        f"{item['name']}: {item['details'].get('blocker', 'blocked')}"
        for item in stages
        if item["status"] == "BLOCKED"
    ]
    failures = [
        f"{item['name']}: {item['details'].get('failures') or item['details'].get('error') or 'failed'}"
        for item in stages
        if item["status"] == "FAIL"
    ]
    return {
        "version": "1.0.0",
        "release_id": os.environ.get("AGROLOG_RELEASE_ID", "local-full-project-gate"),
        "commit_sha": os.environ.get("GITHUB_SHA", "0" * 40),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": evaluation["status"],
        "mode": mode,
        "stages": stages,
        "blockers": blockers,
        "failures": failures,
        "evaluation": evaluation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog MT whole-project final release gate")
    parser.add_argument("--mode", choices=("ci", "final"), default="ci")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--report", default="outputs/full-project-release-gate.json")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    report = build_report(repo, mode=args.mode)
    output = repo / args.report
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "mode": report["mode"],
        "report": str(output),
        "failures": report["failures"],
        "blockers": report["blockers"],
    }, ensure_ascii=False, indent=2))

    if report["status"] == "FAIL":
        return 1
    if args.mode == "final" and report["status"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
