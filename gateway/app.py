from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from google.cloud import bigquery

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
BQ_LOCATION = os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("agrolog.gateway")

app = FastAPI(title="AgroLog Gateway", version="0.2.0")
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
