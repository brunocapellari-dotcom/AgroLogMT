from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from collector.local_analytics_store import LocalAnalyticsStore
from scripts import run_zero_cost_pipeline


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_one_command_imports_authorized_inputs_and_fails_closed_when_report_is_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "runtime"
    output = tmp_path / "output"
    freight = tmp_path / "freight.json"
    market = tmp_path / "market.json"

    freight.write_text(
        json.dumps([
            {
                "publication_id": "pub-1",
                "source_provider": "authorized_local_export",
                "carrier_name": "Transportadora A",
                "municipality_name": "Sorriso",
                "pickup_entity_id": "pickup:caravagio",
                "pickup_name": "Caravagio",
                "destination_name": "Rondonópolis",
                "product_id": "milho",
                "freight_announced_brl_per_t": 170.0,
                "data_publicacao": _now(),
                "data_coleta": _now(),
                "provenance": {"fixture": True},
            }
        ]),
        encoding="utf-8",
    )
    market.write_text(
        json.dumps([
            {
                "product_id": "soja",
                "produto": "Soja",
                "metric_name": "preco_fisico",
                "local": "Mato Grosso",
                "valor": 125.0,
                "unidade_origem": "BRL/sc",
                "data_referencia": datetime.now(timezone.utc).date().isoformat(),
                "data_publicacao": _now(),
                "provenance": {"fixture": True},
            }
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_zero_cost_pipeline.py",
            "--no-collect",
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--freight-input",
            str(freight),
            "--market-input",
            str(market),
            "--market-source-id",
            "fixture_market",
            "--market-source-name",
            "Fixture Market",
            "--market-usage-rights",
            "USER_AUTHORIZED",
            "--market-authorization-basis",
            "test fixture",
        ],
    )

    code = run_zero_cost_pipeline.main()
    assert code == 2

    store = LocalAnalyticsStore(root / "analytics" / "agrolog.duckdb", root / "parquet")
    assert store.scalar("SELECT COUNT(*) FROM logistica.freight_announcements") == 1
    assert store.scalar("SELECT COUNT(*) FROM mercado.market_reference") == 1

    run_manifest = json.loads((root / "last-run.json").read_text(encoding="utf-8"))
    assert run_manifest["sellability"]["status"] == "BLOCKED"
    assert (output / "integrated-report.md").is_file()
    assert (output / "commercial-snapshot.json").is_file()
    assert (output / "sellability.json").is_file()


def test_market_input_requires_explicit_rights_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market = tmp_path / "market.json"
    market.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_zero_cost_pipeline.py",
            "--no-collect",
            "--root",
            str(tmp_path / "runtime"),
            "--market-input",
            str(market),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        run_zero_cost_pipeline.main()
    assert exc.value.code == 2
