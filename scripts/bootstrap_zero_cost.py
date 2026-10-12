from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = ROOT / "requirements-zero-cost.txt"
DEFAULT_VENV = ROOT / ".venv-zero-cost"

FORBIDDEN_REQUIREMENT_TOKENS = (
    "google-cloud",
    "google-api-python-client",
    "google-auth",
    "gcloud",
    "boto3",
    "azure-",
)

REQUIRED_IMPORTS = (
    "duckdb",
    "eccodes",
    "requests",
    "defusedxml",
)


def requirement_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r ") or line.startswith("--requirement "):
            raise ValueError("nested requirements are not allowed in ZERO_COST bootstrap")
        lines.append(line)
    if not lines:
        raise ValueError("requirements-zero-cost.txt cannot be empty")
    return lines


def validate_requirements_policy(lines: Iterable[str]) -> list[str]:
    normalized = [str(line).strip().lower() for line in lines]
    blocked = [
        line
        for line in normalized
        if any(token in line for token in FORBIDDEN_REQUIREMENT_TOKENS)
    ]
    if blocked:
        raise ValueError(
            "ZERO_COST requirements contain cloud/paid-runtime dependencies: "
            + ", ".join(blocked)
        )
    return normalized


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def run_checked(argv: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(argv, cwd=cwd, check=True)


def smoke_imports(python: Path) -> None:
    code = "; ".join(f"import {name}" for name in REQUIRED_IMPORTS)
    run_checked([str(python), "-c", code])


def validate_runtime(python: Path) -> None:
    run_checked([
        str(python),
        str(ROOT / "scripts" / "validate_zero_cost_runtime.py"),
        "--output",
        str(ROOT / "outputs" / "zero-cost-bootstrap-runtime.json"),
    ])


def bootstrap(
    *,
    venv_dir: Path = DEFAULT_VENV,
    requirements: Path = DEFAULT_REQUIREMENTS,
    install: bool = True,
) -> dict:
    lines = requirement_lines(requirements)
    validate_requirements_policy(lines)

    if install:
        if not venv_python(venv_dir).is_file():
            venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
        python = venv_python(venv_dir)
        run_checked([
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--requirement",
            str(requirements),
        ])
    else:
        python = Path(sys.executable)

    smoke_imports(python)
    validate_runtime(python)
    result = {
        "status": "PASS",
        "mode": "ZERO_COST",
        "venv": str(venv_dir),
        "python": str(python),
        "requirements": lines,
        "cloud_dependencies_required": False,
        "paid_runtime_required": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap the minimal AgroLog ZERO_COST local runtime"
    )
    parser.add_argument("--venv", default=str(DEFAULT_VENV))
    parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate policy/imports/runtime using the current Python without installing",
    )
    args = parser.parse_args()

    result = bootstrap(
        venv_dir=Path(args.venv),
        requirements=Path(args.requirements),
        install=not args.check_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
