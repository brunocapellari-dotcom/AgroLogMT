from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from google.cloud import bigquery
from pydantic import BaseModel, ConfigDict, Field, field_validator


class FreightClassification(StrEnum):
    FREIGHT_OFFER = "FREIGHT_OFFER"
    FREIGHT_REQUEST = "FREIGHT_REQUEST"
    UPDATE = "UPDATE"
    CANCELLATION = "CANCELLATION"
    INFORMATION = "INFORMATION"
    IRRELEVANT = "IRRELEVANT"
    UNKNOWN = "UNKNOWN"


class TruthClassification(StrEnum):
    OBSERVED = "OBSERVADO"
    INFERRED = "INFERIDO"
    ESTIMATED = "ESTIMADO"
    EXTERNALLY_CONFIRMED = "CONFIRMADO_EXTERNAMENTE"


class EntityValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_value: str = Field(min_length=1, max_length=1024)
    normalized_value: str | None = Field(default=None, max_length=1024)
    canonical_id: str | None = Field(default=None, max_length=512)
    confidence: float = Field(ge=0.0, le=1.0)


class FreightEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    tenant_id: str = Field(min_length=1, max_length=128)
    classification: FreightClassification
    source_event_ids: list[str] = Field(min_length=1, max_length=100)
    raw_reference: str = Field(min_length=1, max_length=4096)
    timestamp: datetime
    product: str | None = Field(default=None, max_length=128)
    origin: EntityValue | None = None
    destination: EntityValue | None = None
    entities: dict[str, list[EntityValue]] = Field(default_factory=dict)
    rate: Decimal | None = Field(default=None, ge=0)
    rate_unit: str | None = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    truth_classification: TruthClassification
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_event_ids")
    @classmethod
    def unique_source_event_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("source_event_ids must be unique")
        if any(not value or len(value) > 256 for value in values):
            raise ValueError("source_event_ids contain invalid value")
        return values


def _verify_signature(
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    secret: str,
    now: int | None = None,
) -> None:
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="missing integration signature")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid integration timestamp") from exc
    now_epoch = int(time.time()) if now is None else now
    if abs(now_epoch - ts) > 300:
        raise HTTPException(status_code=401, detail="integration timestamp outside replay window")
    expected = hmac.new(
        secret.encode("utf-8"),
        timestamp.encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=401, detail="invalid integration signature")


def _merge_sql(project_id: str, dataset_id: str) -> str:
    return f"""
    MERGE `{project_id}.{dataset_id}.freight_events` T
    USING (
      SELECT
        @event_id AS event_id,
        @event_version AS event_version,
        @tenant_id AS tenant_id,
        @classification AS classification,
        TIMESTAMP(@event_timestamp) AS event_timestamp,
        @product AS product,
        @origin_raw AS origin_raw,
        @origin_normalized AS origin_normalized,
        @origin_canonical_id AS origin_canonical_id,
        @destination_raw AS destination_raw,
        @destination_normalized AS destination_normalized,
        @destination_canonical_id AS destination_canonical_id,
        @rate AS rate,
        @rate_unit AS rate_unit,
        @confidence AS confidence,
        @truth_classification AS truth_classification,
        @source_event_ids AS source_event_ids,
        @raw_reference AS raw_reference,
        @entities_json AS entities_json,
        @metadata_json AS metadata_json,
        @provenance_json AS provenance_json
    ) S
    ON T.event_id = S.event_id AND T.event_version = S.event_version
    WHEN NOT MATCHED THEN INSERT (
        event_id,event_version,tenant_id,classification,event_timestamp,product,
        origin_raw,origin_normalized,origin_canonical_id,
        destination_raw,destination_normalized,destination_canonical_id,
        rate,rate_unit,confidence,truth_classification,source_event_ids,
        raw_reference,entities_json,metadata_json,provenance_json,ingested_at
    ) VALUES (
        S.event_id,S.event_version,S.tenant_id,S.classification,S.event_timestamp,S.product,
        S.origin_raw,S.origin_normalized,S.origin_canonical_id,
        S.destination_raw,S.destination_normalized,S.destination_canonical_id,
        S.rate,S.rate_unit,S.confidence,S.truth_classification,S.source_event_ids,
        S.raw_reference,S.entities_json,S.metadata_json,S.provenance_json,CURRENT_TIMESTAMP()
    )
    """


def _params(
    event: FreightEvent,
) -> list[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]:
    return [
        bigquery.ScalarQueryParameter("event_id", "STRING", event.event_id),
        bigquery.ScalarQueryParameter("event_version", "INT64", event.version),
        bigquery.ScalarQueryParameter("tenant_id", "STRING", event.tenant_id),
        bigquery.ScalarQueryParameter("classification", "STRING", event.classification.value),
        bigquery.ScalarQueryParameter("event_timestamp", "STRING", event.timestamp.isoformat()),
        bigquery.ScalarQueryParameter("product", "STRING", event.product),
        bigquery.ScalarQueryParameter(
            "origin_raw",
            "STRING",
            event.origin.raw_value if event.origin else None,
        ),
        bigquery.ScalarQueryParameter(
            "origin_normalized",
            "STRING",
            event.origin.normalized_value if event.origin else None,
        ),
        bigquery.ScalarQueryParameter(
            "origin_canonical_id",
            "STRING",
            event.origin.canonical_id if event.origin else None,
        ),
        bigquery.ScalarQueryParameter(
            "destination_raw",
            "STRING",
            event.destination.raw_value if event.destination else None,
        ),
        bigquery.ScalarQueryParameter(
            "destination_normalized",
            "STRING",
            event.destination.normalized_value if event.destination else None,
        ),
        bigquery.ScalarQueryParameter(
            "destination_canonical_id",
            "STRING",
            event.destination.canonical_id if event.destination else None,
        ),
        bigquery.ScalarQueryParameter("rate", "NUMERIC", event.rate),
        bigquery.ScalarQueryParameter("rate_unit", "STRING", event.rate_unit),
        bigquery.ScalarQueryParameter("confidence", "FLOAT64", event.confidence),
        bigquery.ScalarQueryParameter(
            "truth_classification",
            "STRING",
            event.truth_classification.value,
        ),
        bigquery.ArrayQueryParameter("source_event_ids", "STRING", event.source_event_ids),
        bigquery.ScalarQueryParameter("raw_reference", "STRING", event.raw_reference),
        bigquery.ScalarQueryParameter(
            "entities_json",
            "STRING",
            json.dumps(
                {
                    key: [value.model_dump(mode="json") for value in values]
                    for key, values in event.entities.items()
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        ),
        bigquery.ScalarQueryParameter(
            "metadata_json",
            "STRING",
            json.dumps(event.metadata, ensure_ascii=False, sort_keys=True),
        ),
        bigquery.ScalarQueryParameter(
            "provenance_json",
            "STRING",
            json.dumps(event.provenance, ensure_ascii=False, sort_keys=True),
        ),
    ]


def create_freight_router(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    *,
    max_bytes_billed: int,
    query_timeout_seconds: int,
) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/freight/events", status_code=status.HTTP_202_ACCEPTED)
    async def ingest_freight_event(
        request: Request,
        x_agrolog_timestamp: str | None = Header(default=None),
        x_agrolog_signature: str | None = Header(default=None),
        x_idempotency_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        secret = os.environ.get("AGROLOG_FREIGHT_SHARED_SECRET")
        if not secret:
            raise HTTPException(status_code=503, detail="freight ingestion is not configured")
        body = await request.body()
        if len(body) > 1_000_000:
            raise HTTPException(status_code=413, detail="freight event payload too large")
        _verify_signature(body, x_agrolog_timestamp, x_agrolog_signature, secret)
        try:
            event = FreightEvent.model_validate_json(body)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid freight event contract") from exc
        expected_key = f"{event.event_id}:{event.version}"
        if x_idempotency_key != expected_key:
            raise HTTPException(status_code=400, detail="invalid idempotency key")

        config = bigquery.QueryJobConfig(
            query_parameters=_params(event),
            maximum_bytes_billed=max_bytes_billed,
            use_query_cache=False,
        )
        try:
            job = client.query(_merge_sql(project_id, dataset_id), job_config=config)
            job.result(timeout=query_timeout_seconds)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="failed to persist freight event") from exc
        return {
            "status": "accepted",
            "event_id": event.event_id,
            "version": event.version,
            "idempotency_key": expected_key,
        }

    return router
