from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.go_live_zero_cost import archive_evidence
from scripts.preflight_zero_cost_local import preflight


def _operator_config(tmp_path: Path) -> Path:
    freight = tmp_path / "inputs" / "freight.json"
    market = tmp_path / "inputs" / "market.csv"
    freight.parent.mkdir(parents=True, exist_ok=True)
    freight.write_text('[{"carrier_name":"A"}]', encoding="utf-8")
    market.write_text("produto,valor\nsoja,120\n", encoding="utf-8")

    config = tmp_path / "config" / "zero_cost_operator.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps({
            "mode": "ZERO_COST",
            "root": "../runtime",
            "output_dir": "../output",
            "uf": "MT",
            "no_collect": False,
            "no_global_public": False,
            "no_weather": False,
            "no_conab": False,
            "freight_input": "../inputs/freight.json",
            "market_input": "../inputs/market.csv",
            "market": {
                "source_id": "authorized_market",
                "source_name": "Authorized Market",
                "usage_rights": "USER_AUTHORIZED",
                "authorization_basis": "contrato interno autorizado",
            },
        }),
        encoding="utf-8",
    )
    return config


def test_preflight_blocks_missing_real_ana_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _operator_config(tmp_path)
    monkeypatch.delenv("ANA_IDENTIFICADOR", raising=False)
    monkeypatch.delenv("ANA_SENHA", raising=False)

    result = preflight(config)

    assert result["status"] == "BLOCKED"
    assert any(
        blocker.startswith("required_ana_credentials_missing:")
        for blocker in result["blockers"]
    )


def test_preflight_passes_with_real_local_inputs_and_ana_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _operator_config(tmp_path)
    monkeypatch.setenv("ANA_IDENTIFICADOR", "configured-in-environment")
    monkeypatch.setenv("ANA_SENHA", "configured-in-environment")

    result = preflight(config)

    assert result["status"] == "PASS"
    assert result["checks"]["ana_credentials_present"] is True
    assert result["checks"]["runtime_imports_present"] is True
    assert result["blockers"] == []


def test_preflight_rejects_placeholder_market_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _operator_config(tmp_path)
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["market"]["authorization_basis"] = "Substitua pela autorização real"
    config.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("ANA_IDENTIFICADOR", "configured")
    monkeypatch.setenv("ANA_SENHA", "configured")

    result = preflight(config)

    assert result["status"] == "BLOCKED"
    assert "market_authorization_basis_is_placeholder" in result["blockers"]


def test_archive_evidence_marks_go_live_pass_only_with_complete_sellable_evidence(
    tmp_path: Path,
) -> None:
    config = _operator_config(tmp_path)
    runtime = tmp_path / "runtime"
    output = tmp_path / "output"
    runtime.mkdir()
    output.mkdir()

    (runtime / "last-run.json").write_text(
        json.dumps({"sellability": {"status": "SELLABLE"}}),
        encoding="utf-8",
    )
    (output / "commercial-snapshot.json").write_text("{}", encoding="utf-8")
    (output / "sellability.json").write_text(
        json.dumps({"status": "SELLABLE", "blockers": []}),
        encoding="utf-8",
    )
    (output / "integrated-report.md").write_text("# Report\n", encoding="utf-8")
    (output / "zero-cost-manifest.json").write_text(
        json.dumps({"paid_runtime_required": False}),
        encoding="utf-8",
    )

    result = archive_evidence(
        config_path=config,
        evidence_root=tmp_path / "evidence",
        pipeline_exit_code=0,
    )

    assert result["status"] == "GO_LIVE_PASS"
    assert result["sellability_status"] == "SELLABLE"
    assert result["missing_evidence"] == []
    assert len(result["evidence"]) == 5
    assert all(item["sha256"] for item in result["evidence"])
    latest = json.loads((tmp_path / "evidence" / "latest.json").read_text(encoding="utf-8"))
    assert latest["status"] == "GO_LIVE_PASS"


def test_archive_evidence_blocks_when_any_required_artifact_is_missing(tmp_path: Path) -> None:
    config = _operator_config(tmp_path)
    runtime = tmp_path / "runtime"
    output = tmp_path / "output"
    runtime.mkdir()
    output.mkdir()
    (runtime / "last-run.json").write_text("{}", encoding="utf-8")
    (output / "sellability.json").write_text(
        json.dumps({"status": "SELLABLE", "blockers": []}),
        encoding="utf-8",
    )

    result = archive_evidence(
        config_path=config,
        evidence_root=tmp_path / "evidence",
        pipeline_exit_code=0,
    )

    assert result["status"] == "GO_LIVE_BLOCKED"
    assert result["missing_evidence"]
