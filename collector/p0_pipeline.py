from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from .cloud_store import DriveBigQueryStore
from .models import SourceSpec
from .orchestrator import CollectorEngine
from .p0_adapters import AnaHidroAdoptedAdapter, BcbPtaxDailyAdapter

PTAX_SOURCE_ID = "bcb_ptax_usd_daily"
ANA_SOURCE_ID = "ana_hidroweb_m04_stations"


def _engine_for(spec: SourceSpec, store: DriveBigQueryStore) -> CollectorEngine:
    def resolver(method: str):
        if method == "bcb_ptax_daily":
            return BcbPtaxDailyAdapter()
        if method == "ana_hidroweb_adopted":
            return AnaHidroAdoptedAdapter()
        from .adapters import get_adapter

        return get_adapter(method)

    return CollectorEngine(store=store, adapter_resolver=resolver)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _ensure_ptax_table(store: DriveBigQueryStore) -> str:
    dataset = os.environ.get("AGROLOG_MERCADO_DATASET", "mercado")
    table = f"{store.project_id}.{dataset}.ptax_usd_daily"
    store.bq.query(
        f"""
        CREATE TABLE IF NOT EXISTS `{table}` (
          data_referencia DATE NOT NULL,
          data_publicacao TIMESTAMP,
          data_coleta TIMESTAMP NOT NULL,
          competencia STRING NOT NULL,
          moeda STRING NOT NULL,
          cotacao_compra FLOAT64 NOT NULL,
          cotacao_venda FLOAT64 NOT NULL,
          data_hora_cotacao TIMESTAMP NOT NULL,
          source_url STRING NOT NULL,
          snapshot_sha256 STRING NOT NULL,
          raw_artifact_ref STRING,
          evidence_class STRING NOT NULL,
          collector_version STRING NOT NULL
        )
        PARTITION BY data_referencia
        CLUSTER BY moeda
        """
    ).result()
    return table


def run_bcb_ptax_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    outcome = _engine_for(spec, store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"acquisition": manifest.to_dict()}
    try:
        payload = json.loads(outcome.payload.decode("utf-8"))
        row = payload["latest"]
        timestamp = str(row["dataHoraCotacao"])
        data_ref = timestamp[:10]
        if len(data_ref) != 10 or data_ref[4] != "-":
            raise ValueError(f"dataHoraCotacao inesperada: {timestamp}")
        table = _ensure_ptax_table(store)
        from google.cloud import bigquery

        check_sql = f"SELECT COUNT(*) n FROM `{table}` WHERE data_referencia=@d AND data_hora_cotacao=@ts"
        job = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("d", "DATE", data_ref),
                bigquery.ScalarQueryParameter("ts", "TIMESTAMP", timestamp),
            ]
        )
        exists = next(iter(store.bq.query(check_sql, job_config=job).result()))["n"] > 0
        inserted = 0
        if not exists:
            insert_row = {
                "data_referencia": data_ref,
                "data_publicacao": timestamp,
                "data_coleta": manifest.data_coleta,
                "competencia": data_ref[:7],
                "moeda": "USD",
                "cotacao_compra": float(row["cotacaoCompra"]),
                "cotacao_venda": float(row["cotacaoVenda"]),
                "data_hora_cotacao": timestamp,
                "source_url": manifest.observed_url,
                "snapshot_sha256": manifest.sha256,
                "raw_artifact_ref": manifest.raw_artifact_ref,
                "evidence_class": "observado",
                "collector_version": manifest.collector_version,
            }
            errors = store.bq.insert_rows_json(table, [insert_row])
            if errors:
                raise RuntimeError(f"BigQuery PTAX insert falhou: {errors}")
            inserted = 1
        return 0, {
            "status": "ok",
            "acquisition": manifest.to_dict(),
            "load": {"table": table, "inserted": inserted, "duplicate": bool(exists), "data_referencia": data_ref},
        }
    except Exception as exc:  # noqa: BLE001
        return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict(), "error": f"{type(exc).__name__}: {exc}"}


def _ensure_ana_table(store: DriveBigQueryStore) -> str:
    dataset = os.environ.get("AGROLOG_HIDRO_DATASET", "hidrologia")
    table = f"{store.project_id}.{dataset}.hydro_station_telemetry"
    store.bq.query(
        f"""
        CREATE TABLE IF NOT EXISTS `{table}` (
          station_code STRING NOT NULL,
          station_name STRING,
          river STRING,
          data_referencia DATE NOT NULL,
          data_publicacao TIMESTAMP,
          data_coleta TIMESTAMP NOT NULL,
          competencia STRING NOT NULL,
          data_hora_medicao TIMESTAMP NOT NULL,
          data_atualizacao TIMESTAMP,
          chuva_mm FLOAT64,
          chuva_status STRING,
          cota_cm FLOAT64,
          cota_status STRING,
          vazao_m3s FLOAT64,
          vazao_status STRING,
          source STRING NOT NULL,
          snapshot_sha256 STRING NOT NULL,
          raw_artifact_ref STRING,
          evidence_class STRING NOT NULL,
          collector_version STRING NOT NULL
        )
        PARTITION BY data_referencia
        CLUSTER BY station_code, river
        """
    ).result()
    return table


def run_ana_hydro_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    outcome = _engine_for(spec, store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"acquisition": manifest.to_dict()}
    try:
        payload = json.loads(outcome.payload.decode("utf-8"))
        if payload.get("token_exposed") is not False:
            raise RuntimeError("SECRET_LEAK_GUARD: token exposure flag inválida")
        items = payload.get("items") or []
        station_meta = {
            "15400000": ("Porto Velho", "Madeira"),
            "15320002": ("Abunã", "Madeira"),
            "15630000": ("Humaitá", "Madeira"),
            "17730000": ("Itaituba", "Tapajós"),
            "17900000": ("Santarém", "Tapajós/Amazonas"),
        }
        rows: list[dict[str, Any]] = []
        for item in items:
            station = str(item.get("codigoestacao") or "").strip()
            measured = str(item.get("Data_Hora_Medicao") or "").strip()
            if not station or not measured:
                continue
            data_ref = measured[:10]
            name, river = station_meta.get(station, (None, None))
            rows.append(
                {
                    "station_code": station,
                    "station_name": name,
                    "river": river,
                    "data_referencia": data_ref,
                    "data_publicacao": item.get("Data_Atualizacao"),
                    "data_coleta": manifest.data_coleta,
                    "competencia": data_ref[:7],
                    "data_hora_medicao": measured,
                    "data_atualizacao": item.get("Data_Atualizacao"),
                    "chuva_mm": _safe_float(item.get("Chuva_Adotada")),
                    "chuva_status": str(item.get("Chuva_Adotada_Status")) if item.get("Chuva_Adotada_Status") is not None else None,
                    "cota_cm": _safe_float(item.get("Cota_Adotada")),
                    "cota_status": str(item.get("Cota_Adotada_Status")) if item.get("Cota_Adotada_Status") is not None else None,
                    "vazao_m3s": _safe_float(item.get("Vazao_Adotada")),
                    "vazao_status": str(item.get("Vazao_Adotada_Status")) if item.get("Vazao_Adotada_Status") is not None else None,
                    "source": "ANA_HIDROWEB_NEW_API",
                    "snapshot_sha256": manifest.sha256,
                    "raw_artifact_ref": manifest.raw_artifact_ref,
                    "evidence_class": "observado",
                    "collector_version": manifest.collector_version,
                }
            )
        if not rows:
            raise RuntimeError("ANA retornou zero registros utilizáveis")
        table = _ensure_ana_table(store)
        from google.cloud import bigquery

        stations = sorted({row["station_code"] for row in rows})
        query = f"""
        SELECT CONCAT(station_code,'|',CAST(data_hora_medicao AS STRING),'|',COALESCE(CAST(data_atualizacao AS STRING),'')) k
        FROM `{table}`
        WHERE data_referencia >= DATE_SUB(CURRENT_DATE(), INTERVAL 45 DAY)
          AND station_code IN UNNEST(@stations)
        """
        job = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("stations", "STRING", stations)]
        )
        existing = {row["k"] for row in store.bq.query(query, job_config=job).result()}
        new_rows = []
        for row in rows:
            key = f"{row['station_code']}|{row['data_hora_medicao']}|{row.get('data_atualizacao') or ''}"
            if key not in existing:
                new_rows.append(row)
        errors = store.bq.insert_rows_json(table, new_rows) if new_rows else []
        if errors:
            raise RuntimeError(f"BigQuery ANA insert falhou: {errors}")
        return 0, {
            "status": "ok",
            "acquisition": manifest.to_dict(),
            "load": {"table": table, "records_read": len(rows), "inserted": len(new_rows), "duplicates_skipped": len(rows) - len(new_rows)},
        }
    except Exception as exc:  # noqa: BLE001
        return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict(), "error": f"{type(exc).__name__}: {exc}"}
