from __future__ import annotations

import json
from pathlib import Path

from collector.argentina_estimaciones import ArgentinaCropRecord
from collector.models import RunManifest
from collector.usda_wasde import WasdeArtifact, WasdeCell
from collector.zero_cost_pipeline import ZeroCostRuntime
from collector.zero_cost_public_sources import (
    persist_ana_payload,
    persist_argentina_records,
    persist_wasde_cells,
)
from models.zero_cost_snapshot import build_zero_cost_snapshot
from scripts.build_zero_cost_bundle import build_bundle


def _manifest(source_id: str) -> RunManifest:
    return RunManifest(
        source_id=source_id,
        group="dados",
        started_at="2026-10-09T12:00:00+00:00",
        finished_at="2026-10-09T12:00:01+00:00",
        status="updated",
        collector_version="test",
        data_coleta="2026-10-09T12:00:01+00:00",
        observed_url="https://example.invalid/source",
        raw_artifact_ref="/tmp/raw",
        sha256="a" * 64,
    )


def test_ana_local_persistence_and_snapshot(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    payload = json.dumps({
        "token_exposed": False,
        "items": [{
            "codigoestacao": "15400000",
            "Data_Hora_Medicao": "2026-10-09T11:00:00+00:00",
            "Data_Atualizacao": "2026-10-09T11:05:00+00:00",
            "Chuva_Adotada": "2.5",
            "Cota_Adotada": "123.0",
            "Vazao_Adotada": "456.0",
        }],
    }).encode()
    first = persist_ana_payload(runtime, manifest=_manifest("ana_hidroweb_m04_stations"), payload=payload)
    assert first["inserted"] == 1
    second = persist_ana_payload(runtime, manifest=_manifest("ana_hidroweb_m04_stations"), payload=payload)
    assert second["inserted"] == 0
    snapshot = build_zero_cost_snapshot(runtime.analytics)
    hydro = next(item for item in snapshot["components"] if item["component"] == "hydrology")
    assert hydro["data"][0]["river"] == "Madeira"
    assert hydro["data"][0]["flow_m3s"] == 456.0
    assert Path(first["parquet"]).is_file()


def test_argentina_local_persistence_current_view_and_bundle(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    records = [
        ArgentinaCropRecord(
            source_id="sagyp_argentina",
            crop="Soja",
            crop_id="soja",
            year=2026,
            season="2025/26",
            province="Cordoba",
            province_id="14",
            department="Rio Cuarto",
            department_id="14098",
            planted_area_ha=1000.0,
            harvested_area_ha=950.0,
            production_t=3000.0,
            yield_kg_ha=3158.0,
        )
    ]
    result = persist_argentina_records(
        runtime,
        records,
        snapshot_id="argentina:test",
        source_hash="b" * 64,
        data_coleta="2026-10-09T12:00:00+00:00",
        source_url="https://datos.magyp.gob.ar/test.csv",
        raw_artifact_ref="/tmp/ar.csv",
        source_updated_at="2026-10-08T12:00:00+00:00",
    )
    assert result["inserted"] == 1
    duplicate = persist_argentina_records(
        runtime,
        records,
        snapshot_id="argentina:test",
        source_hash="b" * 64,
        data_coleta="2026-10-09T12:00:00+00:00",
        source_url="https://datos.magyp.gob.ar/test.csv",
        raw_artifact_ref="/tmp/ar.csv",
        source_updated_at="2026-10-08T12:00:00+00:00",
    )
    assert duplicate["inserted"] == 0
    snapshot = build_zero_cost_snapshot(runtime.analytics)
    argentina = next(item for item in snapshot["components"] if item["component"] == "argentina")
    assert argentina["data"][0]["crop_id"] == "soja"
    assert argentina["data"][0]["production_t"] == 3000.0
    snapshot_path, _ = build_bundle(snapshot, tmp_path / "static")
    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["delivery_mode"] == "ZERO_COST"
    assert Path(result["parquet"]).is_file()


def test_wasde_local_persistence_and_commodity_hint(tmp_path: Path) -> None:
    runtime = ZeroCostRuntime(tmp_path)
    artifact = WasdeArtifact(
        url="https://esmis.nal.usda.gov/sites/default/release-files/x/wasde1026.xml",
        format="xml",
        year=2026,
        month=10,
    )
    cells = [
        WasdeCell(
            cell_index=0,
            path="wasde/commodity/value",
            attributes_json=json.dumps({"commodity.name": "Soybeans", "value.unit": "million_t"}, sort_keys=True),
            raw_text="120.5",
            numeric_value=120.5,
        )
    ]
    result = persist_wasde_cells(
        runtime,
        cells,
        artifact=artifact,
        payload=b"<wasde/>",
        data_coleta="2026-10-09T12:00:00+00:00",
        publication_date="2026-10-09",
        raw_artifact_ref="/tmp/wasde.xml",
    )
    assert result["inserted"] == 1
    duplicate = persist_wasde_cells(
        runtime,
        cells,
        artifact=artifact,
        payload=b"<wasde/>",
        data_coleta="2026-10-09T12:00:00+00:00",
        publication_date="2026-10-09",
        raw_artifact_ref="/tmp/wasde.xml",
    )
    assert duplicate["inserted"] == 0
    snapshot = build_zero_cost_snapshot(runtime.analytics)
    usda = next(item for item in snapshot["components"] if item["component"] == "usda")
    assert usda["data"]
    assert usda["data"][0]["commodity_hint"] == "soja"
    assert usda["data"][0]["numeric_value"] == 120.5
    assert Path(result["parquet"]).is_file()


def test_zero_cost_public_source_module_has_no_gcp_runtime_dependency() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "collector" / "zero_cost_public_sources.py").read_text(encoding="utf-8").lower()
    assert "google.cloud" not in text
    assert "gcloud " not in text
    assert "bigquery.client" not in text
