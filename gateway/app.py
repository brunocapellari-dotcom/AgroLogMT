from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google.cloud import bigquery

from .intelligence_queries import (
    build_biomass_sql,
    build_fertilizer_imports_sql,
    build_freight_lanes_sql,
    build_hydrology_latest_sql,
    build_imea_freight_reference_sql,
    build_overview_sql,
    build_ptax_current_sql,
    build_storage_balance_sql,
)
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
INTELLIGENCE_DATASET_ID = safe_identifier(
    os.environ.get("AGROLOG_INTELLIGENCE_DATASET", "marts_agrolog360"), label="intelligence_dataset"
)
BQ_LOCATION = os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
BQ_MAX_BYTES_BILLED = int(os.environ.get("AGROLOG_BQ_MAX_BYTES_BILLED", "1000000000"))
BQ_QUERY_TIMEOUT_SECONDS = int(os.environ.get("AGROLOG_BQ_QUERY_TIMEOUT_SECONDS", "30"))
ENABLE_DOCS = os.environ.get("AGROLOG_ENABLE_DOCS", "0") == "1"
PILOT_PORTS = {
    "SANTOS": "Santos",
    "PARANAGUA": "Paranaguá",
    "BARCARENA_VILA_DO_CONDE": "Barcarena / Vila do Conde",
    "SANTAREM": "Santarém",
    "ITAQUI": "Itaqui",
}
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "cross-origin-opener-policy": "same-origin",
    "cross-origin-resource-policy": "same-origin",
    "content-security-policy": (
        "default-src 'self'; "
        "base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; "
        "script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob: https:; font-src 'self' data: https:; "
        "connect-src 'self' https:; worker-src 'self' blob:"
    ),
}

if BQ_MAX_BYTES_BILLED <= 0:
    raise RuntimeError("AGROLOG_BQ_MAX_BYTES_BILLED deve ser positivo")
if not 1 <= BQ_QUERY_TIMEOUT_SECONDS <= 120:
    raise RuntimeError("AGROLOG_BQ_QUERY_TIMEOUT_SECONDS deve estar entre 1 e 120")

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("agrolog.gateway")

app = FastAPI(
    title="AgroLog Gateway",
    version="0.4.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)


def _cors_origins() -> list[str]:
    values = [
        value.strip()
        for value in os.environ.get(
            "AGROLOG_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if value.strip()
    ]
    for value in values:
        if value == "*":
            raise RuntimeError("CORS wildcard é proibido no AgroLog Gateway")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError(f"origem CORS inválida: {value}")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("HTTP em CORS é permitido somente para desenvolvimento local")
    return values


cors_origins = _cors_origins()
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["authorization", "content-type", "x-request-id"],
        expose_headers=["x-request-id"],
        max_age=600,
    )

client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)


def _request_id(value: str | None) -> str:
    if value and REQUEST_ID_RE.fullmatch(value):
        return value
    return str(uuid.uuid4())


@app.middleware("http")
async def audit_request(request: Request, call_next):
    request_id = _request_id(request.headers.get("x-request-id"))
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        if request.url.path.startswith("/v1/") or request.url.path == "/healthz":
            response.headers["cache-control"] = "no-store, max-age=0"
            response.headers["pragma"] = "no-cache"
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
        config = bigquery.QueryJobConfig(
            query_parameters=parameters,
            maximum_bytes_billed=BQ_MAX_BYTES_BILLED,
            use_query_cache=True,
        )
        job = client.query(sql, job_config=config)
        return [dict(row.items()) for row in job.result(timeout=BQ_QUERY_TIMEOUT_SECONDS)]
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


@app.get("/v1/intelligence/overview")
def intelligence_overview(uf: str | None = "MT") -> dict[str, Any]:
    try:
        uf = normalize_uf(uf)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sql = build_overview_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID)
    rows = _query(sql, [bigquery.ScalarQueryParameter("uf", "STRING", uf)])
    return {
        "source_id": "marts_agrolog360.overview_current_v1",
        "evidence_class": "DERIVED",
        "filters": {"uf": uf},
        "data": _jsonable(rows[0] if rows else {}),
    }


@app.get("/v1/intelligence/storage-balance")
def intelligence_storage_balance(
    uf: str | None = "MT",
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    try:
        uf = normalize_uf(uf)
        limit = normalize_limit(limit, maximum=100)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    sql = build_storage_balance_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID)
    params = [
        bigquery.ScalarQueryParameter("uf", "STRING", uf),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "marts_agrolog360.storage_balance_v1",
        "evidence_class": "INFERIDO",
        "filters": {"uf": uf, "limit": limit},
        "data": [_jsonable(row) for row in _query(sql, params)],
    }


@app.get("/v1/intelligence/freight-lanes")
def intelligence_freight_lanes(
    origin: str | None = None,
    destination: str | None = None,
    product: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    try:
        limit = normalize_limit(limit, maximum=500)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    params = [
        bigquery.ScalarQueryParameter("origin", "STRING", origin),
        bigquery.ScalarQueryParameter("destination", "STRING", destination),
        bigquery.ScalarQueryParameter("product", "STRING", product),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    rows = [_jsonable(row) for row in _query(build_freight_lanes_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID), params)]
    return {
        "source_id": "marts_agrolog360.freight_lanes_v1",
        "evidence_class": "DERIVED_FROM_OBSERVED_OFFERS_NOT_EXECUTED_FREIGHT",
        "filters": {"origin": origin, "destination": destination, "product": product, "limit": limit},
        "data": rows,
    }


@app.get("/v1/intelligence/fertilizers")
def intelligence_fertilizers(
    uf: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    try:
        uf = normalize_uf(uf)
        limit = normalize_limit(limit, maximum=500)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    params = [
        bigquery.ScalarQueryParameter("uf", "STRING", uf),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "marts_agrolog360.fertilizer_imports_v1",
        "evidence_class": "OBSERVED_CUSTOMS_AGGREGATE",
        "filters": {"uf": uf, "limit": limit},
        "data": [_jsonable(row) for row in _query(build_fertilizer_imports_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID), params)],
    }


@app.get("/v1/intelligence/biomass")
def intelligence_biomass(
    geo_id: str | None = "MT",
    biomass_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    try:
        limit = normalize_limit(limit, maximum=500)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    params = [
        bigquery.ScalarQueryParameter("geo_id", "STRING", geo_id),
        bigquery.ScalarQueryParameter("biomass_type", "STRING", biomass_type),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "marts_agrolog360.biomass_v1",
        "evidence_class": "MIXED_EXPLICIT",
        "filters": {"geo_id": geo_id, "biomass_type": biomass_type, "limit": limit},
        "data": [_jsonable(row) for row in _query(build_biomass_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID), params)],
    }


@app.get("/v1/intelligence/hydrology")
def intelligence_hydrology(
    river: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    try:
        limit = normalize_limit(limit, maximum=200)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    params = [
        bigquery.ScalarQueryParameter("river", "STRING", river),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "marts_agrolog360.hydrology_latest_v1",
        "evidence_class": "DERIVADO_DE_OBSERVADO",
        "filters": {"river": river, "limit": limit},
        "data": [_jsonable(row) for row in _query(build_hydrology_latest_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID), params)],
    }


@app.get("/v1/intelligence/ptax")
def intelligence_ptax(currency: str | None = "USD") -> dict[str, Any]:
    normalized = currency.strip().upper() if currency else None
    if normalized is not None and (len(normalized) != 3 or not normalized.isalpha()):
        raise HTTPException(status_code=400, detail="currency deve ser código alfabético de 3 letras")
    params = [bigquery.ScalarQueryParameter("currency", "STRING", normalized)]
    rows = _query(build_ptax_current_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID), params)
    return {
        "source_id": "marts_agrolog360.ptax_current_v1",
        "evidence_class": "OBSERVADO",
        "filters": {"currency": normalized},
        "data": _jsonable(rows[0] if rows else {}),
    }


@app.get("/v1/intelligence/imea-freight-reference")
def intelligence_imea_freight_reference(
    origin: str | None = None,
    destination: str | None = None,
    product: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    try:
        limit = normalize_limit(limit, maximum=500)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    params = [
        bigquery.ScalarQueryParameter("origin", "STRING", origin),
        bigquery.ScalarQueryParameter("destination", "STRING", destination),
        bigquery.ScalarQueryParameter("product", "STRING", product),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "marts_agrolog360.imea_freight_reference_v1",
        "evidence_class": "SOURCE_DECLARED",
        "route_type": "UNCLASSIFIED",
        "filters": {"origin": origin, "destination": destination, "product": product, "limit": limit},
        "data": [_jsonable(row) for row in _query(build_imea_freight_reference_sql(PROJECT_ID, INTELLIGENCE_DATASET_ID), params)],
    }


UI_DIR = Path(os.environ.get("AGROLOG_MARITIME_UI_DIR", "/app/maritime_ui/dist"))
if UI_DIR.is_dir():
    app.mount("/maritime", StaticFiles(directory=str(UI_DIR), html=True), name="maritime-ui")
