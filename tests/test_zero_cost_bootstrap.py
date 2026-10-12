from __future__ import annotations

from pathlib import Path

import pytest

from scripts.bootstrap_zero_cost import (
    FORBIDDEN_REQUIREMENT_TOKENS,
    REQUIRED_IMPORTS,
    requirement_lines,
    validate_requirements_policy,
    venv_python,
)


ROOT = Path(__file__).resolve().parents[1]


def test_zero_cost_requirements_are_minimal_and_cloud_free() -> None:
    lines = requirement_lines(ROOT / "requirements-zero-cost.txt")
    normalized = validate_requirements_policy(lines)

    assert any(line.startswith("duckdb") for line in normalized)
    assert any(line.startswith("eccodes") for line in normalized)
    assert any(line.startswith("requests") for line in normalized)
    assert any(line.startswith("defusedxml") for line in normalized)
    assert all(
        token not in line
        for line in normalized
        for token in FORBIDDEN_REQUIREMENT_TOKENS
    )


def test_zero_cost_runtime_imports_are_available() -> None:
    for name in REQUIRED_IMPORTS:
        __import__(name)


def test_zero_cost_requirements_reject_cloud_dependency(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text("duckdb>=1,<2\ngoogle-cloud-bigquery>=3,<4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cloud/paid-runtime dependencies"):
        validate_requirements_policy(requirement_lines(path))


def test_zero_cost_requirements_reject_nested_requirement_files(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text("-r requirements-cloud.txt\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nested requirements"):
        requirement_lines(path)


def test_venv_python_is_platform_specific(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import scripts.bootstrap_zero_cost as bootstrap

    monkeypatch.setattr(bootstrap.os, "name", "nt")
    assert venv_python(tmp_path) == tmp_path / "Scripts" / "python.exe"
    monkeypatch.setattr(bootstrap.os, "name", "posix")
    assert venv_python(tmp_path) == tmp_path / "bin" / "python"
