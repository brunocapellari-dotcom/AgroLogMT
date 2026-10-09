from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_zero_cost_bundle import build_bundle, validate_snapshot
from scripts.validate_zero_cost_runtime import ROOT, validate


def test_zero_cost_contract_has_zero_cost_ceiling() -> None:
    policy = json.loads((ROOT / "contracts" / "zero_cost_runtime.v1.json").read_text(encoding="utf-8"))
    assert policy["mode"] == "ZERO_COST"
    assert policy["max_implementation_cost_brl"] == 0
    assert policy["max_recurring_cost_brl"] == 0
    assert policy["mandatory_paid_services"] == []
    assert policy["mandatory_cloud_services"] == []


def test_zero_cost_validator_passes_without_cloud_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "AGROLOG_GCP_PROJECT"):
        monkeypatch.delenv(key, raising=False)
    result = validate(tmp_path / "result.json")
    assert result["status"] == "PASS"
    assert result["paid_runtime_required"] is False
    assert result["cloud_credentials_required"] is False


def test_static_bundle_is_generated_and_marks_zero_cost(tmp_path: Path) -> None:
    snapshot = {
        "product": "AGROLOG INTELLIGENCE",
        "components": [{"component": "market", "status": "READY", "data": [{"value": 1}]}],
    }
    snapshot_path, manifest_path = build_bundle(snapshot, tmp_path)
    saved = json.loads(snapshot_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["delivery_mode"] == "ZERO_COST"
    assert manifest["mode"] == "ZERO_COST"
    assert manifest["paid_runtime_required"] is False
    assert manifest["cloud_credentials_required"] is False
    assert len(manifest["sha256"]) == 64


def test_static_bundle_rejects_nonempty_secret_fields(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        build_bundle(
            {"product": "AGROLOG INTELLIGENCE", "components": [], "api_token": "do-not-publish"},
            tmp_path,
        )


def test_zero_cost_static_dashboard_does_not_require_gateway() -> None:
    page = (ROOT / "maritime_ui" / "public" / "zero-cost.html").read_text(encoding="utf-8")
    assert "./data/commercial-snapshot.json" in page
    assert "/v1/" not in page
