from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from collector.argentina_estimaciones import ArgentinaCropRecord
from collector.conab_safra import ConabSafraRecord
from collector.models import RunManifest, SourceSpec
from collector.usda_wasde import WasdeArtifact, WasdeCell
from collector.zero_cost_conab import canonical_conab_row, persist_conab_rows
from collector.zero_cost_pipeline import ZeroCostRuntime
from collector.zero_cost_public_sources import (
    persist_ana_payload,
    persist_argentina_records,
    persist_wasde_cells,
)
from collector.zero_cost_weather import persist_gfs_rows
from scripts import run_zero_cost_pipeline


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _manifest(source_id: str, now: datetime, *, sha: str) -> RunManifest:
    return RunManifest(
        source_id=source_id,
        group="dados",
        started_at=(now - timedelta(seconds=1)).isoformat(),
        finished_at=now.isoformat(),
        status="updated",
        collector_version="e2e",
        data_coleta=now.isoformat(),
        observed_url="https://example.invalid/e2e",
        raw_artifact_ref="/tmp/e2e",
        sha256=sha,
    )


def _seed_ptax(runtime: ZeroCostRuntime, now: datetime) -> None:
    spec = SourceSpec(
        source_id="bcb_ptax_usd_daily",
        name="PTAX",
        group="dados",
        method="bcb_ptax_daily",
        file_extension="json",
    )
    payload = json.dumps({
        "latest": {
            "dataHoraCotacao": now.isoformat(),
            "cotacaoCompra": 5.30,
            "cotacaoVenda": 5.31,
        }
    }).encode()
    runtime.persist_ptax_capture(
        spec,
        _manifest("bcb_ptax_usd_daily", now, sha="a" * 64),
        payload,
    )


def _seed_conab(runtime: ZeroCostRuntime, now: datetime) -> None:
    snapshot_id = "b" * 64
    records = [
        ConabSafraRecord(
            source_id="conab_safra_graos_xlsx",
            geo_level="uf",
            geo_id="MT",
            produto_origem="SOJA",
            product_id="soja",
            safra="2026/27",
            vintage_position="current",
            area_mil_ha=13000.0,
            produtividade_kg_ha=3600.0,
            producao_mil_t=46800.0,
            area_var_pct=1.0,
            produtividade_var_pct=1.5,
            producao_var_pct=2.5,
            identity_error_mil_t=0.0,
            identity_error_pct=0.0,
            quality_score=1.0,
            quality_flags=(),
            source_sheet="MT",
            source_row=10,
        ),
        ConabSafraRecord(
            source_id="conab_safra_graos_xlsx",
            geo_level="uf",
            geo_id="MT",
            produto_origem="MILHO TOTAL",
            product_id="milho_total",
            safra="2026/27",
            vintage_position="current",
            area_mil_ha=7500.0,
            produtividade_kg_ha=6500.0,
            producao_mil_t=48750.0,
            area_var_pct=1.0,
            produtividade_var_pct=1.0,
            producao_var_pct=2.0,
            identity_error_mil_t=0.0,
            identity_error_pct=0.0,
            quality_score=1.0,
            quality_flags=(),
            source_sheet="MT",
            source_row=11,
        ),
        ConabSafraRecord(
            source_id="conab_safra_graos_xlsx",
            geo_level="country",
            geo_id="BR",
            produto_origem="SOJA",
            product_id="soja",
            safra="2026/27",
            vintage_position="current",
            area_mil_ha=49000.0,
            produtividade_kg_ha=3500.0,
            producao_mil_t=171500.0,
            area_var_pct=1.0,
            produtividade_var_pct=1.0,
            producao_var_pct=2.0,
            identity_error_mil_t=0.0,
            identity_error_pct=0.0,
            quality_score=1.0,
            quality_flags=(),
            source_sheet="BR",
            source_row=20,
        ),
        ConabSafraRecord(
            source_id="conab_safra_graos_xlsx",
            geo_level="country",
            geo_id="BR",
            produto_origem="MILHO TOTAL",
            product_id="milho_total",
            safra="2026/27",
            vintage_position="current",
            area_mil_ha=23000.0,
            produtividade_kg_ha=5900.0,
            producao_mil_t=135700.0,
            area_var_pct=1.0,
            produtividade_var_pct=1.0,
            producao_var_pct=2.0,
            identity_error_mil_t=0.0,
            identity_error_pct=0.0,
            quality_score=1.0,
            quality_flags=(),
            source_sheet="BR",
            source_row=21,
        ),
    ]
    rows = [
        canonical_conab_row(
            record,
            snapshot_id=snapshot_id,
            data_coleta=now.isoformat(),
            raw_artifact_ref="/tmp/conab.xlsx",
            observed_url="https://www.gov.br/conab/e2e.xlsx",
            publication=now,
        )
        for record in records
    ]
    persist_conab_rows(runtime, rows, snapshot_id=snapshot_id)


def _seed_comex(runtime: ZeroCostRuntime, now: datetime) -> None:
    snapshot_id = "c" * 64
    competence = now.strftime("%Y-%m")
    rows = [{
        "snapshot_id": snapshot_id,
        "record_id": "e2e-comex-soja",
        "data_referencia": now.date().replace(day=1).isoformat(),
        "competencia": competence,
        "flow": "export",
        "ncm_code": "12019000",
        "ncm_name": "Soja",
        "state_filter_id": "51",
        "state_name": "Mato Grosso",
        "country_code": "160",
        "country_name": "China",
        "via_code": "1",
        "via_name": "Marítima",
        "urf_code": "1",
        "urf_name": "Porto",
        "kg_liquido": 1_000_000,
        "valor_fob_usd": 400_000,
        "data_publicacao": now.date().isoformat(),
        "data_coleta": now.isoformat(),
        "source_url": "https://api-comexstat.mdic.gov.br",
        "source_hash": snapshot_id,
        "raw_artifact_ref": "/tmp/comex.json",
        "evidence_class": "observado",
        "collector_version": "e2e",
    }]
    runtime.persist_comex_rows(rows, snapshot_id)


def _seed_hydrology(runtime: ZeroCostRuntime, now: datetime) -> None:
    payload = json.dumps({
        "token_exposed": False,
        "items": [{
            "codigoestacao": "17730000",
            "Data_Hora_Medicao": now.isoformat(),
            "Data_Atualizacao": now.isoformat(),
            "Chuva_Adotada": "2.5",
            "Cota_Adotada": "123.0",
            "Vazao_Adotada": "456.0",
        }],
    }).encode()
    persist_ana_payload(
        runtime,
        manifest=_manifest("ana_hidroweb_m04_stations", now, sha="d" * 64),
        payload=payload,
    )


def _seed_argentina(runtime: ZeroCostRuntime, now: datetime) -> None:
    records = [
        ArgentinaCropRecord(
            source_id="sagyp_argentina",
            crop="Soja",
            crop_id="soja",
            year=now.year,
            season=f"{now.year - 1}/{str(now.year)[-2:]}",
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
    persist_argentina_records(
        runtime,
        records,
        snapshot_id="argentina:e2e",
        source_hash="e" * 64,
        data_coleta=now.isoformat(),
        source_url="https://datos.magyp.gob.ar/e2e.csv",
        raw_artifact_ref="/tmp/argentina.csv",
        source_updated_at=now.isoformat(),
    )


def _seed_wasde(runtime: ZeroCostRuntime, now: datetime) -> None:
    artifact = WasdeArtifact(
        url="https://esmis.nal.usda.gov/e2e/wasde.xml",
        format="xml",
        year=now.year,
        month=now.month,
    )
    cells = [
        WasdeCell(
            cell_index=0,
            path="wasde/commodity/value",
            attributes_json=json.dumps({
                "commodity.name": "Soybeans",
                "value.unit": "million_t",
            }, sort_keys=True),
            raw_text="120.5",
            numeric_value=120.5,
        )
    ]
    persist_wasde_cells(
        runtime,
        cells,
        artifact=artifact,
        payload=b"<wasde/>",
        data_coleta=now.isoformat(),
        publication_date=now.date().isoformat(),
        raw_artifact_ref="/tmp/wasde.xml",
    )


def _seed_weather(runtime: ZeroCostRuntime, now: datetime) -> None:
    init = now.replace(minute=0, second=0)
    rows = []
    for hour in (72, 168, 360):
        for variable, value, unit in (
            ("temperature_2m", 29.0, "C"),
            ("precipitation_period", 12.0, "mm"),
        ):
            rows.append({
                "record_id": f"e2e:{hour}:{variable}",
                "source_id": "gfs_nomads",
                "model": "GFS",
                "run_id": f"gfs_{init:%Y%m%dT%H%MZ}",
                "initialization_time": init.isoformat(),
                "forecast_hour": hour,
                "valid_time": (init + timedelta(hours=hour)).isoformat(),
                "collection_time": now.isoformat(),
                "geo_id": "SORRISO_MT",
                "latitude": -12.5425,
                "longitude": -55.7211,
                "grid_latitude": -12.5,
                "grid_longitude": 304.25,
                "variable": variable,
                "value": value,
                "unit": unit,
                "interval_start_hour": hour - 6 if variable == "precipitation_period" else None,
                "interval_end_hour": hour,
                "resolution": "0.25deg",
                "model_count": 1,
                "evidence_class": "PREVISTO",
                "raw_artifact_ref": f"/tmp/gfs-f{hour:03d}.grib2",
                "source_hash": "f" * 64,
                "source_url": "https://nomads.ncep.noaa.gov/",
            })
    persist_gfs_rows(runtime, rows)


def _seed_public_components(runtime: ZeroCostRuntime, now: datetime) -> None:
    _seed_ptax(runtime, now)
    _seed_conab(runtime, now)
    _seed_comex(runtime, now)
    _seed_hydrology(runtime, now)
    _seed_argentina(runtime, now)
    _seed_wasde(runtime, now)
    _seed_weather(runtime, now)


def test_zero_cost_local_e2e_reaches_sellable_without_cloud(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = _now()
    root = tmp_path / "runtime"
    output = tmp_path / "output"
    runtime = ZeroCostRuntime(root)
    _seed_public_components(runtime, now)

    freight = tmp_path / "freight.json"
    freight.write_text(json.dumps([
        {
            "publication_id": "pub-e2e-1",
            "source_provider": "authorized_local_export",
            "carrier_name": "Transportadora A",
            "municipality_name": "Sorriso",
            "pickup_entity_id": "pickup:caravagio",
            "pickup_name": "Caravagio",
            "destination_name": "Rondonópolis",
            "product_id": "milho",
            "freight_announced_brl_per_t": 170.0,
            "data_publicacao": now.isoformat(),
            "data_coleta": now.isoformat(),
            "provenance": {"fixture": True},
        }
    ]), encoding="utf-8")

    market = tmp_path / "market.json"
    market.write_text(json.dumps([
        {
            "product_id": "soja",
            "produto": "Soja",
            "metric_name": "preco_fisico",
            "local": "Mato Grosso",
            "valor": 125.0,
            "unidade_origem": "BRL/sc",
            "data_referencia": now.date().isoformat(),
            "data_publicacao": now.isoformat(),
            "provenance": {"fixture": True},
        },
        {
            "product_id": "milho_total",
            "produto": "Milho",
            "metric_name": "preco_fisico",
            "local": "Mato Grosso",
            "valor": 52.0,
            "unidade_origem": "BRL/sc",
            "data_referencia": now.date().isoformat(),
            "data_publicacao": now.isoformat(),
            "provenance": {"fixture": True},
        },
    ]), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_zero_cost_pipeline.py",
            "--no-collect",
            "--root", str(root),
            "--output-dir", str(output),
            "--freight-input", str(freight),
            "--market-input", str(market),
            "--market-source-id", "authorized_market_e2e",
            "--market-source-name", "Authorized Market E2E",
            "--market-usage-rights", "USER_AUTHORIZED",
            "--market-authorization-basis", "deterministic E2E fixture",
        ],
    )

    code = run_zero_cost_pipeline.main()
    assert code == 0

    manifest = json.loads((root / "last-run.json").read_text(encoding="utf-8"))
    snapshot = json.loads((output / "commercial-snapshot.json").read_text(encoding="utf-8"))
    sellability = json.loads((output / "sellability.json").read_text(encoding="utf-8"))
    report = (output / "integrated-report.md").read_text(encoding="utf-8")

    assert manifest["paid_runtime_required"] is False
    assert manifest["cloud_credentials_required"] is False
    assert manifest["sellability"]["status"] == "SELLABLE"
    assert snapshot["commercial_input_gate"]["status"] == "PASS"
    assert sellability["status"] == "SELLABLE"
    assert sellability["blockers"] == []
    assert "**Status comercial:** SELLABLE" in report
    assert "frete anunciado R$ 170,00/t" in report
    assert "Authorized Market E2E" not in report
    assert "authorized_market_e2e" in report
    assert "BigQuery" not in report
    assert "Cloud Run" not in report
