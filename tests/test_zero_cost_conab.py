from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from collector.conab_safra import ConabSafraRecord
from collector.zero_cost_conab import canonical_conab_row, persist_conab_rows
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.zero_cost_snapshot import build_zero_cost_snapshot
from scripts.build_zero_cost_bundle import build_bundle


def _record(*, geo_level: str, geo_id: str, product_id: str, label: str) -> ConabSafraRecord:
    return ConabSafraRecord(
        source_id="conab_safra_graos_xlsx",
        geo_level=geo_level,
        geo_id=geo_id,
        produto_origem=label,
        product_id=product_id,
        safra="25/26",
        vintage_position="current",
        area_mil_ha=13000.0,
        produtividade_kg_ha=4000.0,
        producao_mil_t=52000.0,
        area_var_pct=1.0,
        produtividade_var_pct=2.0,
        producao_var_pct=3.0,
        identity_error_mil_t=0.0,
        identity_error_pct=0.0,
        quality_score=1.0,
        quality_flags=(),
        source_sheet=geo_id,
        source_row=10,
    )


def test_conab_local_persistence_materializes_mt_and_br(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    publication = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    snapshot_id = "c" * 64
    rows = [
        canonical_conab_row(
            _record(geo_level="uf", geo_id="MT", product_id="soja", label="SOJA"),
            snapshot_id=snapshot_id,
            data_coleta="2026-10-09T12:05:00+00:00",
            raw_artifact_ref="/tmp/conab.xlsx",
            observed_url="https://www.gov.br/conab/file.xlsx",
            publication=publication,
        ),
        canonical_conab_row(
            _record(geo_level="country", geo_id="BR", product_id="milho_total", label="MILHO TOTAL"),
            snapshot_id=snapshot_id,
            data_coleta="2026-10-09T12:05:00+00:00",
            raw_artifact_ref="/tmp/conab.xlsx",
            observed_url="https://www.gov.br/conab/file.xlsx",
            publication=publication,
        ),
    ]
    first = persist_conab_rows(runtime, rows, snapshot_id=snapshot_id)
    assert first["inserted"] == 2
    duplicate = persist_conab_rows(runtime, rows, snapshot_id=snapshot_id)
    assert duplicate["inserted"] == 0

    snapshot = build_zero_cost_snapshot(runtime.analytics, uf="MT")
    mt = next(item for item in snapshot["components"] if item["component"] == "crops_mt")
    br = next(item for item in snapshot["components"] if item["component"] == "crops_br")
    assert mt["data"][0]["product_id"] == "soja"
    assert mt["data"][0]["vintage_position"] == "current"
    assert br["data"][0]["product_id"] == "milho_total"
    assert mt["data"][0]["producao_mil_t"] == 52000.0
    assert Path(first["parquet"]).is_file()

    snapshot_path, _ = build_bundle(snapshot, tmp_path / "static")
    assert snapshot_path.is_file()


def test_conab_record_id_is_stable_for_same_snapshot_and_key() -> None:
    publication = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    record = _record(geo_level="uf", geo_id="MT", product_id="soja", label="SOJA")
    kwargs = {
        "snapshot_id": "d" * 64,
        "data_coleta": "2026-10-09T12:05:00+00:00",
        "raw_artifact_ref": None,
        "observed_url": None,
        "publication": publication,
    }
    assert canonical_conab_row(record, **kwargs)["record_id"] == canonical_conab_row(record, **kwargs)["record_id"]


def test_conab_tie_out_fails_closed(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    publication = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    snapshot_id = "e" * 64
    row = canonical_conab_row(
        _record(geo_level="uf", geo_id="MT", product_id="soja", label="SOJA"),
        snapshot_id=snapshot_id,
        data_coleta="2026-10-09T12:05:00+00:00",
        raw_artifact_ref=None,
        observed_url=None,
        publication=publication,
    )
    persist_conab_rows(runtime, [row], snapshot_id=snapshot_id)
    altered = dict(row)
    altered["record_id"] = "different"
    try:
        persist_conab_rows(runtime, [row, altered], snapshot_id=snapshot_id)
    except RuntimeError as exc:
        assert "Tie-out CONAB" in str(exc)
    else:
        raise AssertionError("CONAB tie-out should fail closed")


def test_zero_cost_conab_module_has_no_gcp_runtime_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "collector" / "zero_cost_conab.py").read_text(encoding="utf-8").lower()
    assert "google.cloud" not in text
    assert "gcloud " not in text
    assert "bigquery.client" not in text
