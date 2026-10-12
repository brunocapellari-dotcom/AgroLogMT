from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_zero_cost_operator import build_pipeline_args, load_operator_config


def test_operator_config_builds_single_zero_cost_command_without_code_edits(tmp_path: Path) -> None:
    config_path = tmp_path / "zero_cost_operator.json"
    config_path.write_text(
        json.dumps({
            "mode": "ZERO_COST",
            "root": "runtime",
            "output_dir": "output",
            "uf": "MT",
            "freight_input": "inputs/freight.json",
            "market_input": "inputs/market.csv",
            "market": {
                "source_id": "authorized_market",
                "source_name": "Authorized Market",
                "usage_rights": "USER_AUTHORIZED",
                "authorization_basis": "explicit operator authorization",
            },
        }),
        encoding="utf-8",
    )

    config = load_operator_config(config_path)
    argv = build_pipeline_args(config, config_path=config_path)

    assert "--root" in argv
    assert "--output-dir" in argv
    assert "--freight-input" in argv
    assert "--market-input" in argv
    assert "--market-source-id" in argv
    assert "--market-usage-rights" in argv
    assert "USER_AUTHORIZED" in argv
    assert str((tmp_path / "inputs/freight.json").resolve()) in argv
    assert str((tmp_path / "inputs/market.csv").resolve()) in argv


def test_operator_config_requires_market_rights_metadata(tmp_path: Path) -> None:
    config_path = tmp_path / "zero_cost_operator.json"
    config_path.write_text(
        json.dumps({
            "mode": "ZERO_COST",
            "market_input": "inputs/market.csv",
            "market": {
                "source_id": "authorized_market",
                "source_name": "Authorized Market"
            },
        }),
        encoding="utf-8",
    )
    config = load_operator_config(config_path)
    with pytest.raises(ValueError, match="market_input requires market metadata"):
        build_pipeline_args(config, config_path=config_path)


def test_operator_config_rejects_non_zero_cost_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "zero_cost_operator.json"
    config_path.write_text(json.dumps({"mode": "GCP"}), encoding="utf-8")
    with pytest.raises(ValueError, match="mode must be ZERO_COST"):
        load_operator_config(config_path)
