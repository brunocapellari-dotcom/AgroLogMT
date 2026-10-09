from __future__ import annotations

import json
from pathlib import Path

from collector.local_analytics_store import LocalAnalyticsStore
from collector.models import RunManifest, SourceSpec
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.zero_cost_snapshot import build_zero_cost_snapshot
from scripts.build_zero_cost_bundle import build_bundle


def _manifest() -> RunManifest:
    return RunManifest(
        source_id="bcb_ptax_usd_daily",
        group="dados",
        started_at="2026-10-09T12:00:00+00:00",
        finished_at="2026-10-09T12:00:01+00:00",
        status="updated",
        collector_version="test",
        data_coleta="2026-10-09T12:00:01+00:00",
        observed_url="https://www4.bcb.gov.br/Download/fechamento/20261009.csv",
        raw_artifact_ref="/tmp/ptax.csv",
        sha256="a" * 64,
    )


def test_local_analytics_store_round_trip_and_parquet(tmp_path: Path) -> None:
    store = LocalAnalyticsStore(tmp_path / "agrolog.duckdb", tmp_path / "parquet")
    store.ensure_table("testdata", "rows", {"id": "BIGINT", "name": "VARCHAR"})
    assert store.insert_rows(
        "testdata", "rows", [{"id": 1, "name": "soja"}], columns=["id", "name"]
    ) == 1
    assert store.query("SELECT id, name FROM testdata.rows") == [{"id": 1, "name": "soja"}]
    parquet = store.export_table_parquet("testdata", "rows")
    assert parquet.is_file()
    assert parquet.stat().st_size > 0
    manifest = store.manifest()
    assert manifest["paid_runtime_required"] is False
    assert manifest["cloud_credentials_required"] is False


def test_ptax_persists_to_duckdb_and_snapshot_without_gcp(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    spec = SourceSpec(
        source_id="bcb_ptax_usd_daily",
        name="PTAX",
        group="dados",
        method="bcb_ptax_daily",
        file_extension="csv",
    )
    payload = json.dumps({
        "latest": {
            "dataHoraCotacao": "2026-10-09T13:10:00-03:00",
            "cotacaoCompra": 5.31,
            "cotacaoVenda": 5.32,
        }
    }).encode()
    load = runtime.persist_ptax_capture(spec, _manifest(), payload)
    assert load["inserted"] == 1
    second = runtime.persist_ptax_capture(spec, _manifest(), payload)
    assert second["inserted"] == 0
    snapshot = build_zero_cost_snapshot(runtime.analytics, uf="MT")
    ptax = next(item for item in snapshot["components"] if item["component"] == "ptax")
    assert ptax["data"][0]["cotacao_venda"] == 5.32
    assert snapshot["delivery_mode"] == "ZERO_COST"
    assert snapshot["analytical_backend"] == "duckdb"
    snapshot_path, manifest_path = build_bundle(snapshot, tmp_path / "static")
    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["delivery_mode"] == "ZERO_COST"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["paid_runtime_required"] is False


def test_comex_local_tie_out_and_exports_component(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    rows = [
        {
            "snapshot_id": "b" * 64,
            "record_id": "r1",
            "data_referencia": "2026-09-01",
            "competencia": "2026-09",
            "flow": "export",
            "ncm_code": "12019000",
            "ncm_name": "Soja",
            "state_filter_id": "52",
            "state_name": "Mato Grosso",
            "country_code": "160",
            "country_name": "China",
            "via_code": "1",
            "via_name": "Maritima",
            "urf_code": "1",
            "urf_name": "Porto",
            "kg_liquido": 1_000_000,
            "valor_fob_usd": 400_000,
            "data_publicacao": "2026-10-05",
            "data_coleta": "2026-10-09T12:00:00+00:00",
            "source_url": "https://api-comexstat.mdic.gov.br",
            "source_hash": "b" * 64,
            "raw_artifact_ref": "/tmp/comex.json",
            "evidence_class": "observado",
            "collector_version": "test",
        }
    ]
    first = runtime.persist_comex_rows(rows, "b" * 64)
    assert first["inserted"] == 1
    second = runtime.persist_comex_rows(rows, "b" * 64)
    assert second["inserted"] == 0
    snapshot = build_zero_cost_snapshot(runtime.analytics, uf="MT")
    exports = next(item for item in snapshot["components"] if item["component"] == "exports")
    assert exports["data"][0]["product_id"] == "soja_grao"
    assert exports["data"][0]["toneladas"] == 1000.0


def test_zero_cost_scripts_do_not_reference_gcp_commands() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "scripts/run_zero_cost_pipeline.py",
        "scripts/build_zero_cost_outputs.py",
        "collector/local_analytics_store.py",
        "collector/zero_cost_pipeline.py",
    ):
        text = (root / relative).read_text(encoding="utf-8").lower()
        assert "gcloud " not in text
        assert "bigquery.client" not in text
