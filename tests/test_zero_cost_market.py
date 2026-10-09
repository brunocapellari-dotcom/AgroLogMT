from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from collector.zero_cost_market import (
    MarketAuthorization,
    persist_market_references,
)
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.commercial_report_builder import build_report_sections
from models.zero_cost_snapshot import build_zero_cost_snapshot


AUTH = MarketAuthorization(
    source_id="authorized_market_fixture",
    source_name="Authorized Market Fixture",
    usage_rights="USER_AUTHORIZED",
    authorization_basis="explicit user-provided commercial-use fixture",
)


def _market_row(*, product_id: str, value: float, date: str = "2026-10-09") -> dict:
    return {
        "product_id": product_id,
        "produto": "Soja" if product_id == "soja" else "Milho",
        "metric_name": "preco_fisico",
        "local": "Mato Grosso",
        "valor": value,
        "unidade_origem": "BRL/sc",
        "unidade_canonica": "BRL/sc",
        "data_referencia": date,
        "data_publicacao": f"{date}T12:00:00-04:00",
        "provenance": {"fixture": True},
    }


def test_market_import_requires_explicit_usage_rights_and_basis(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    invalid = MarketAuthorization(
        source_id="x",
        source_name="X",
        usage_rights="UNKNOWN",
        authorization_basis="",
    )
    with pytest.raises(ValueError):
        persist_market_references(
            runtime,
            [_market_row(product_id="soja", value=125.0)],
            authorization=invalid,
        )


def test_market_import_is_idempotent_and_preserves_same_date_revision(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    t1 = datetime(2026, 10, 9, 16, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 9, 17, 0, tzinfo=timezone.utc)

    first = persist_market_references(
        runtime,
        [_market_row(product_id="soja", value=125.0)],
        authorization=AUTH,
        collected_at=t1,
    )
    duplicate = persist_market_references(
        runtime,
        [_market_row(product_id="soja", value=125.0)],
        authorization=AUTH,
        collected_at=t1,
    )
    revised = persist_market_references(
        runtime,
        [_market_row(product_id="soja", value=127.0)],
        authorization=AUTH,
        collected_at=t2,
    )

    assert first["records_inserted"] == 1
    assert duplicate["records_inserted"] == 0
    assert duplicate["duplicates"] == 1
    assert revised["records_inserted"] == 1
    assert runtime.analytics.scalar(
        "SELECT COUNT(*) FROM mercado.market_reference"
    ) == 2

    snapshot = build_zero_cost_snapshot(runtime.analytics)
    component = next(
        item for item in snapshot["components"]
        if item["component"] == "market_reference"
    )
    assert component["status"] == "FRESH"
    assert len(component["data"]) == 1
    assert component["data"][0]["valor"] == 127.0
    assert component["data"][0]["source_id"] == AUTH.source_id
    assert component["data"][0]["usage_rights"] == "USER_AUTHORIZED"


def test_report_uses_real_market_source_not_hardcoded_imea() -> None:
    snapshot = {
        "components": [
            {
                "component": "ptax",
                "source_id": "local.mercado.ptax_usd_daily",
                "status": "FRESH",
                "data": [{"cotacao_venda": 5.20}],
            },
            {
                "component": "market_reference",
                "source_id": "local.mercado.market_reference",
                "status": "FRESH",
                "data": [
                    {
                        **_market_row(product_id="soja", value=125.0),
                        "source_id": AUTH.source_id,
                        "usage_rights": AUTH.usage_rights,
                        "historical_percentile": 50.0,
                    },
                    {
                        **_market_row(product_id="milho_total", value=52.0),
                        "source_id": AUTH.source_id,
                        "usage_rights": AUTH.usage_rights,
                        "historical_percentile": 50.0,
                    },
                ],
            },
            {
                "component": "crops_mt",
                "source_id": "local.agro.conab_safra_graos",
                "status": "FRESH",
                "data": [
                    {
                        "product_id": "soja",
                        "safra": "2025/26",
                        "vintage_position": "current",
                        "producao_mil_t": 50000.0,
                        "produtividade_kg_ha": 3600.0,
                    },
                    {
                        "product_id": "milho_total",
                        "safra": "2025/26",
                        "vintage_position": "current",
                        "producao_mil_t": 52000.0,
                        "produtividade_kg_ha": 6200.0,
                    },
                ],
            },
        ]
    }
    sections = build_report_sections(snapshot)

    assert sections["Mercado"].status == "READY"
    assert sections["Soja"].status == "READY"
    assert sections["Milho"].status == "READY"
    assert AUTH.source_id in sections["Mercado"].source_ids
    assert AUTH.source_id in sections["Soja"].source_ids
    assert AUTH.source_id in sections["Milho"].source_ids
    assert all("imea" not in source.lower() for source in sections["Mercado"].source_ids)


def test_market_import_rejects_sensitive_credentials(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    row = _market_row(product_id="soja", value=125.0)
    row["api_key"] = "must-not-be-stored"
    with pytest.raises(ValueError, match="sensitive field"):
        persist_market_references(runtime, [row], authorization=AUTH)
