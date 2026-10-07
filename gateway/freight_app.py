from __future__ import annotations

import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from google.cloud import bigquery

from .freight_ingest import create_freight_router
from .storage_queries import safe_identifier

PROJECT_ID = safe_identifier(
    os.environ.get("GOOGLE_CLOUD_PROJECT")
    or os.environ.get("AGROLOG_GCP_PROJECT")
    or "",
    label="project",
)
FREIGHT_DATASET_ID = safe_identifier(
    os.environ.get("AGROLOG_FREIGHT_DATASET", "logistica"),
    label="freight_dataset",
)
BQ_LOCATION = os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
BQ_MAX_BYTES_BILLED = int(
    os.environ.get("AGROLOG_BQ_MAX_BYTES_BILLED", "100000000")
)
BQ_QUERY_TIMEOUT_SECONDS = int(
    os.environ.get("AGROLOG_BQ_QUERY_TIMEOUT_SECONDS", "15")
)
REQUEST_ID_MAX = 128

if BQ_MAX_BYTES_BILLED <= 0:
    raise RuntimeError("AGROLOG_BQ_MAX_BYTES_BILLED must be positive")
if not 1 <= BQ_QUERY_TIMEOUT_SECONDS <= 120:
    raise RuntimeError("AGROLOG_BQ_QUERY_TIMEOUT_SECONDS must be between 1 and 120")

logger = logging.getLogger("agrolog.freight_ingest")
client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)

app = FastAPI(
    title="AgroLog Freight Ingest",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(
    create_freight_router(
        client,
        PROJECT_ID,
        FREIGHT_DATASET_ID,
        max_bytes_billed=BQ_MAX_BYTES_BILLED,
        query_timeout_seconds=BQ_QUERY_TIMEOUT_SECONDS,
    )
)


def _request_id(value: str | None) -> str:
    if value and 1 <= len(value) <= REQUEST_ID_MAX and all(
        ch.isalnum() or ch in "._:-" for ch in value
    ):
        return value
    return str(uuid.uuid4())


@app.middleware("http")
async def secure_request_logging(request: Request, call_next):
    request_id = _request_id(request.headers.get("x-request-id"))
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["x-request-id"] = request_id
        response.headers["cache-control"] = "no-store, max-age=0"
        response.headers["pragma"] = "no-cache"
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        return response
    finally:
        logger.info(
            json.dumps(
                {
                    "event": "freight_ingest_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                },
                sort_keys=True,
            )
        )


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    if not os.environ.get("AGROLOG_FREIGHT_SHARED_SECRET"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="freight secret unavailable",
        )
    try:
        client.get_table(f"{PROJECT_ID}.{FREIGHT_DATASET_ID}.freight_events")
    except Exception as exc:
        logger.warning(
            json.dumps(
                {
                    "event": "freight_readiness_failed",
                    "dependency": "bigquery.freight_events",
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="freight storage unavailable",
        ) from exc
    return {"status": "ready"}
