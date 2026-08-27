from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery

from .maritime_queries import (
    build_lineup_reconciliation_sql,
    build_live_vessels_sql,
    build_port_summary_sql,
    build_vessel_replay_sql,
    normalize_mmsi,
    normalize_port_id,
)
from .storage_queries import (
    build_latest_summary_sql,
    build_latest_warehouses_sql,
    normalize_limit,
    normalize_uf,
    safe_identifier,
)

PROJECT_ID = safe_identifier(
    os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AGROLOG_GCP_PROJECT") or "",
    label="project",
)
DATASET_ID = safe_identifier(os.environ.get("AGROLOG_LOGISTICA_DATASET", "logistica"), label="dataset")
MARITIME_DATASET_ID = safe_identifier(
    os.environ.get("AGROLOG_MARITIME_DATASET", "agrolog_models"), label="maritime_dataset"
)
BQ_LOCATION = os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
PILOT_PORTS = {
    "SANTOS": "Santos",
    "PARANAGUA": "Paranaguá",
    "BARCARENA_VILA_DO_CONDE": "Barcarena / Vila do Conde",
    "SANTAREM": "Santarém",
    "ITAQUI": "Itaqui",
}

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("agrolog.gateway")

app = FastAPI(title="AgroLog Gateway", version="0.3.0")

cors_origins = [
    value.strip()
    for value in os.environ.get(
        "AGROLOG_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if value.strip()
]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)


@app.middleware("http")
async def audit_request(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        return response
    finally:
        payload = {
            "event": "gateway_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
        logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _params(uf: str | None, municipio: str | None, limit: int | None = None) -> list[bigquery.ScalarQueryParameter]:
    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("uf", "STRING", uf),
        bigquery.ScalarQueryParameter("municipio", "STRING", municipio),
    ]
    if limit is not None:
        params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))
    return params


def _query(sql: str, parameters: list[bigquery.ScalarQueryParameter]) -> list[dict[str, Any]]:
    try:
        config = bigquery.QueryJobConfig(query_parameters=parameters)
        return [dict(row.items()) for row in client.query(sql, job_config=config).result()]
    except Exception as exc:
        logger.exception(json.dumps({
            "event": "bigquery_error",
            "error_type": type(exc).__name__,
        }, sort_keys=True))
        raise HTTPException(status_code=502, detail="Falha controlada ao consultar a fonte analítica") from exc


def _port(value: str | None) -> str | None:
    try:
        normalized = normalize_port_id(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if normalized is not None and normalized not in PILOT_PORTS:
        raise HTTPException(status_code=400, detail="port_id fora do piloto Maritime V1")
    return normalized


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/storage/conab/summary")
def storage_summary(uf: str | None = None, municipio: str | None = None) -> dict[str, Any]:
    try:
        uf = normalize_uf(uf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    municipio = municipio.strip() if municipio else None
    sql = build_latest_summary_sql(PROJECT_ID, DATASET_ID)
    rows = _query(sql, _params(uf, municipio))
    return {
        "source_id": "conab_armazens_cadastrados",
        "evidence_class": "observado",
        "filters": {"uf": uf, "municipio": municipio},
        "data": _jsonable(rows[0] if rows else {}),
    }


@app.get("/v1/storage/conab/warehouses")
def storage_warehouses(
    uf: str | None = None,
    municipio: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        uf = normalize_uf(uf)
        limit = normalize_limit(limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    municipio = municipio.strip() if municipio else None
    sql = build_latest_warehouses_sql(PROJECT_ID, DATASET_ID)
    rows = [_jsonable(row) for row in _query(sql, _params(uf, municipio, limit))]
    return {
        "source_id": "conab_armazens_cadastrados",
        "evidence_class": "observado",
        "filters": {"uf": uf, "municipio": municipio, "limit": limit},
        "data": rows,
    }


@app.get("/v1/maritime/config")
def maritime_config() -> dict[str, Any]:
    return {
        "version": "maritime-v1",
        "pilot_ports": [{"port_id": key, "name": value} for key, value in PILOT_PORTS.items()],
        "evidence_rule": "AIS e line-up permanecem observacoes distintas; realizado exige fonte operacional observada.",
    }


@app.get("/v1/maritime/vessels")
def maritime_vessels(
    port_id: str | None = None,
    hours: int = Query(default=6, ge=1, le=168),
    limit: int = Query(default=2000, ge=1, le=5000),
) -> dict[str, Any]:
    port_id = _port(port_id)
    sql = build_live_vessels_sql(PROJECT_ID, MARITIME_DATASET_ID)
    params = [
        bigquery.ScalarQueryParameter("port_id", "STRING", port_id),
        bigquery.ScalarQueryParameter("hours", "INT64", hours),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    rows = [_jsonable(row) for row in _query(sql, params)]
    return {
        "source_id": "shipping_ais_positions",
        "evidence_class": "AIS_OBSERVED",
        "filters": {"port_id": port_id, "hours": hours, "limit": limit},
        "data": rows,
    }


@app.get("/v1/maritime/vessels/{mmsi}/replay")
def maritime_vessel_replay(
    mmsi: str,
    hours: int = Query(default=24, ge=1, le=720),
    end_at: datetime | None = None,
    limit: int = Query(default=10000, ge=2, le=20000),
) -> dict[str, Any]:
    try:
        mmsi = normalize_mmsi(mmsi)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sql = build_vessel_replay_sql(PROJECT_ID, MARITIME_DATASET_ID)
    params = [
        bigquery.ScalarQueryParameter("mmsi", "STRING", mmsi),
        bigquery.ScalarQueryParameter("hours", "INT64", hours),
        bigquery.ScalarQueryParameter("end_at", "TIMESTAMP", end_at),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    rows = [_jsonable(row) for row in _query(sql, params)]
    return {
        "source_id": "shipping_ais_positions",
        "evidence_class": "AIS_OBSERVED",
        "filters": {"mmsi": mmsi, "hours": hours, "end_at": _jsonable(end_at), "limit": limit},
        "data": rows,
    }


@app.get("/v1/maritime/lineup")
def maritime_lineup(
    port_id: str | None = None,
    past_hours: int = Query(default=24, ge=0, le=168),
    future_hours: int = Query(default=336, ge=1, le=1080),
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict[str, Any]:
    port_id = _port(port_id)
    sql = build_lineup_reconciliation_sql(PROJECT_ID, MARITIME_DATASET_ID)
    params = [
        bigquery.ScalarQueryParameter("port_id", "STRING", port_id),
        bigquery.ScalarQueryParameter("past_hours", "INT64", past_hours),
        bigquery.ScalarQueryParameter("future_hours", "INT64", future_hours),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    rows = [_jsonable(row) for row in _query(sql, params)]
    return {
        "source_id": "shipping_lineup_calls_x_shipping_reconciliation",
        "evidence_class": "MIXED_EXPLICIT",
        "filters": {
            "port_id": port_id,
            "past_hours": past_hours,
            "future_hours": future_hours,
            "limit": limit,
        },
        "data": rows,
    }


@app.get("/v1/maritime/summary")
def maritime_summary(
    port_id: str | None = None,
    hours: int = Query(default=24, ge=1, le=168),
    future_hours: int = Query(default=336, ge=1, le=1080),
) -> dict[str, Any]:
    port_id = _port(port_id)
    sql = build_port_summary_sql(PROJECT_ID, MARITIME_DATASET_ID)
    params = [
        bigquery.ScalarQueryParameter("port_id", "STRING", port_id),
        bigquery.ScalarQueryParameter("hours", "INT64", hours),
        bigquery.ScalarQueryParameter("future_hours", "INT64", future_hours),
    ]
    rows = _query(sql, params)
    return {
        "source_id": "maritime_v1_summary",
        "evidence_class": "DERIVED_FROM_OBSERVED_AND_RECONCILED",
        "filters": {"port_id": port_id, "hours": hours, "future_hours": future_hours},
        "data": _jsonable(rows[0] if rows else {}),
    }
