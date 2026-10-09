from __future__ import annotations

from pathlib import Path

from collector.zero_cost_conab import persist_conab_rows
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.zero_cost_snapshot import build_zero_cost_snapshot


def _row(*, geo_level: str, geo_id: str, product_id: str, position: str, production: float) -> dict:
    snapshot = "c" * 64
    return {
        "snapshot_id": snapshot,
        "record_id": f"{geo_level}:{geo_id}:{product_id}:{position}",
        "source_id": "conab_safra_graos_xlsx",
        "geo_level": geo_level,
        "geo_id": geo_id,
        "produto_origem": product_id,
        "product_id": product_id,
        "safra": "2025/26" if position == "current" else "2024/25",
        "vintage_position": position,
        "area_mil_ha": 1000.0,
        "produtividade_kg_ha": 3500.0,
        "producao_mil_t": production,
        "area_var_pct": 1.0 if position == "current" else None,
        "produtividade_var_pct": 2.0 if position == "current" else None,
        "producao_var_pct": 3.0 if position == "current" else None,
        "identity_error_mil_t": 0.0,
        "identity_error_pct": 0.0,
        "quality_score": 1.0,
        "quality_flags": [],
        "source_sheet": geo_id,
        "source_row": 10,
        "data_referencia": "2026-10-08",
        "data_publicacao": "2026-10-08T12:00:00+00:00",
        "data_coleta": "2026-10-09T12:00:00+00:00",
        "data_disponibilidade": "2026-10-08T12:00:00+00:00",
        "availability_verified": True,
        "availability_basis": "official_page_timestamp",
        "competencia": "2026-10",
        "evidence_class": "estimado",
        "methodology_id": "conab_safra_graos_monthly_v1",
        "raw_artifact_ref": "/tmp/conab.xlsx",
        "source_url": "https://www.gov.br/conab/test.xlsx",
        "source_hash": snapshot,
        "collector_version": "test",
        "parser_version": "conab_safra_v1",
    }


def test_conab_local_persistence_is_idempotent_and_materializes_mt_br(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    rows = [
        _row(geo_level="uf", geo_id="MT", product_id="soja", position="previous", production=3400.0),
        _row(geo_level="uf", geo_id="MT", product_id="soja", position="current", production=3500.0),
        _row(geo_level="uf", geo_id="MT", product_id="milho_total", position="current", production=4200.0),
        _row(geo_level="country", geo_id="BR", product_id="soja", position="current", production=170000.0),
    ]
    first = persist_conab_rows(runtime, rows, snapshot_id="c" * 64)
    assert first["inserted"] == 4
    assert Path(first["parquet"]).is_file()

    duplicate = persist_conab_rows(runtime, rows, snapshot_id="c" * 64)
    assert duplicate["inserted"] == 0

    snapshot = build_zero_cost_snapshot(runtime.analytics, uf="MT")
    crops_mt = next(item for item in snapshot["components"] if item["component"] == "crops_mt")
    crops_br = next(item for item in snapshot["components"] if item["component"] == "crops_br")

    assert crops_mt["status"] == "FRESH"
    assert crops_br["status"] == "FRESH"
    current_soy = next(
        row for row in crops_mt["data"]
        if row["product_id"] == "soja" and row["vintage_position"] == "current"
    )
    assert current_soy["producao_mil_t"] == 3500.0
    assert current_soy["delta_producao_pct"] == 3.0
    assert crops_br["data"][0]["geo_id"] == "BR"


def test_zero_cost_conab_module_has_no_direct_gcp_runtime_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "collector" / "zero_cost_conab.py").read_text(encoding="utf-8").lower()
    assert "gcloud " not in text
    assert "google.cloud" not in text
    assert "bigquery.client" not in text
