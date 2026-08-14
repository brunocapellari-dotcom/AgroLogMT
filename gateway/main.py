from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Query, Request, Response
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import bigquery

from gateway.config import ConfigurationError, load_settings
from gateway.query import MAX_LIMIT, QueryValidationError, build_armazens_query


logger = logging.getLogger("agrolog.gateway")
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(
    title="AgroLog Gateway",
    version="0.1.0",
    description="Camada controlada de consulta aos dados analíticos do AgroLog MT.",
)


def _log_event(event: str, **fields: object) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "agrolog-gateway"}


@app.get("/v1/armazens")
def list_armazens(
    request: Request,
    response: Response,
    uf: str | None = Query(default=None, min_length=2, max_length=2),
    municipio: str | None = Query(default=None, max_length=120),
    identificacao_armazem: str | None = Query(default=None, max_length=180),
    limit: int = Query(default=100, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    started = time.perf_counter()
    incoming_request_id = (request.headers.get("x-request-id") or "").strip()
    request_id = incoming_request_id[:128] or str(uuid.uuid4())
    response.headers["x-request-id"] = request_id

    try:
        settings = load_settings()
        query = build_armazens_query(
            settings,
            uf=uf,
            municipio=municipio,
            identificacao_armazem=identificacao_armazem,
            limit=limit,
            offset=offset,
        )
    except (ConfigurationError, QueryValidationError) as exc:
        _log_event(
            "gateway_request_rejected",
            request_id=request_id,
            reason=str(exc),
        )
        status = 503 if isinstance(exc, ConfigurationError) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    try:
        client = bigquery.Client(
            project=settings.project_id,
            location=settings.bq_location,
        )
        job_config = bigquery.QueryJobConfig(
            query_parameters=query.parameters,
            use_query_cache=True,
            maximum_bytes_billed=settings.max_bytes_billed,
        )
        job = client.query(
            query.sql,
            job_config=job_config,
            location=settings.bq_location,
        )
        rows = list(job.result())
        records = [dict(row.items()) for row in rows]
    except (GoogleAPIError, GoogleAuthError) as exc:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        _log_event(
            "gateway_bigquery_error",
            request_id=request_id,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            filters=query.normalized_filters,
        )
        raise HTTPException(
            status_code=502,
            detail="Falha ao consultar a camada analítica.",
        ) from exc

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    total_bytes_processed = getattr(job, "total_bytes_processed", None)
    job_id = getattr(job, "job_id", None)

    _log_event(
        "gateway_query_ok",
        request_id=request_id,
        duration_ms=duration_ms,
        rows_returned=len(records),
        filters=query.normalized_filters,
        bigquery_job_id=job_id,
        total_bytes_processed=total_bytes_processed,
    )

    return {
        "meta": {
            "request_id": request_id,
            "source": settings.armazens_table_ref,
            "classification": "observado",
            "filters": query.normalized_filters,
            "rows_returned": len(records),
            "limit": limit,
            "offset": offset,
            "bigquery_job_id": job_id,
            "total_bytes_processed": total_bytes_processed,
            "duration_ms": duration_ms,
        },
        "data": records,
    }
