from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
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

app = FastAPI(title="AgroLog Gateway", version="0.1.0")
client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)


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
    config = bigquery.QueryJobConfig(query_parameters=_params(uf, municipio))
    rows = [dict(row.items()) for row in client.query(sql, job_config=config).result()]
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
    config = bigquery.QueryJobConfig(query_parameters=_params(uf, municipio, limit))
    rows = [_jsonable(dict(row.items())) for row in client.query(sql, job_config=config).result()]
    return {
        "source_id": "conab_armazens_cadastrados",
        "evidence_class": "observado",
        "filters": {"uf": uf, "municipio": municipio, "limit": limit},
        "data": rows,
    }
