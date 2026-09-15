from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from google.cloud import bigquery

from .pecuaria_queries import (
    build_beef_export_history_sql,
    build_beef_exports_sql,
    build_cattle_municipal_history_sql,
    build_cattle_state_history_sql,
    build_sigsif_current_sql,
    build_slaughter_quarterly_sql,
    load_beef_ncms,
)
from .storage_queries import safe_identifier

router = APIRouter(prefix="/v1/pecuaria", tags=["pecuaria"])
logger = logging.getLogger("agrolog.gateway.pecuaria")

PROJECT_ID = safe_identifier(
    os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("AGROLOG_GCP_PROJECT") or "",
    label="project",
)
PECUARIA_DATASET = safe_identifier(os.environ.get("AGROLOG_PECUARIA_DATASET", "pecuaria"), label="pecuaria_dataset")
TRADE_DATASET = safe_identifier(os.environ.get("AGROLOG_TRADE_DATASET", "comercio_exterior"), label="trade_dataset")
BQ_LOCATION = os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
CONTRACT_PATH = Path(os.environ.get("AGROLOG_TRADE_CODES_CONTRACT", "/app/contracts/product_trade_codes.v1.json"))
BEEF_NCMS = load_beef_ncms(CONTRACT_PATH)
client = bigquery.Client(project=PROJECT_ID, location=BQ_LOCATION)


def _jsonable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _query(sql: str, parameters: list[Any]) -> list[dict[str, Any]]:
    try:
        cfg = bigquery.QueryJobConfig(query_parameters=parameters)
        return [_jsonable(dict(row.items())) for row in client.query(sql, job_config=cfg).result()]
    except Exception as exc:
        logger.exception("pecuaria_bigquery_error", extra={"error_type": type(exc).__name__})
        raise HTTPException(status_code=502, detail="Falha controlada ao consultar a inteligência pecuária") from exc


def _year_range(year_start: int | None, year_end: int | None) -> tuple[int | None, int | None]:
    if year_start is not None and year_end is not None and year_start > year_end:
        raise HTTPException(status_code=400, detail="year_start não pode ser maior que year_end")
    return year_start, year_end


def _competence(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", text):
        raise HTTPException(status_code=400, detail=f"{label} deve usar YYYY-MM")
    return text


def _country_code(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text or len(text) > 16 or not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise HTTPException(status_code=400, detail="country_code inválido")
    return text


@router.get("/herd/state")
def cattle_state_history(
    year_start: int | None = Query(default=None, ge=1974, le=2100),
    year_end: int | None = Query(default=None, ge=1974, le=2100),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    year_start, year_end = _year_range(year_start, year_end)
    sql = build_cattle_state_history_sql(PROJECT_ID, PECUARIA_DATASET)
    params = [
        bigquery.ScalarQueryParameter("year_start", "INT64", year_start),
        bigquery.ScalarQueryParameter("year_end", "INT64", year_end),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "ibge_sidra_ppm_3939",
        "evidence_class": "observado",
        "temporal_warning": "Série realizada; disponibilidade histórica de cada vintage não foi reconstruída.",
        "filters": {"year_start": year_start, "year_end": year_end, "limit": limit},
        "data": _query(sql, params),
    }


@router.get("/herd/municipal")
def cattle_municipal_history(
    ibge_code: str | None = None,
    municipio: str | None = None,
    year_start: int | None = Query(default=None, ge=1974, le=2100),
    year_end: int | None = Query(default=None, ge=1974, le=2100),
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, Any]:
    year_start, year_end = _year_range(year_start, year_end)
    if ibge_code is not None:
        ibge_code = ibge_code.strip()
        if not re.fullmatch(r"\d{7}", ibge_code):
            raise HTTPException(status_code=400, detail="ibge_code deve ter 7 dígitos")
    municipio_pattern = None
    if municipio is not None:
        municipio = municipio.strip()
        if not municipio or len(municipio) > 120:
            raise HTTPException(status_code=400, detail="municipio inválido")
        municipio_pattern = f"%{municipio.casefold()}%"
    sql = build_cattle_municipal_history_sql(PROJECT_ID, PECUARIA_DATASET)
    params = [
        bigquery.ScalarQueryParameter("ibge_code", "STRING", ibge_code),
        bigquery.ScalarQueryParameter("municipio_pattern", "STRING", municipio_pattern),
        bigquery.ScalarQueryParameter("year_start", "INT64", year_start),
        bigquery.ScalarQueryParameter("year_end", "INT64", year_end),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "ibge_sidra_ppm_3939",
        "evidence_class": "observado",
        "temporal_warning": "Série realizada; não usar como feature point-in-time sem vintage comprovado.",
        "filters": {
            "ibge_code": ibge_code,
            "municipio": municipio,
            "year_start": year_start,
            "year_end": year_end,
            "limit": limit,
        },
        "data": _query(sql, params),
    }


@router.get("/slaughter/quarterly")
def cattle_slaughter_quarterly(
    year_start: int | None = Query(default=None, ge=1997, le=2100),
    year_end: int | None = Query(default=None, ge=1997, le=2100),
    quarter: int | None = Query(default=None, ge=1, le=4),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    year_start, year_end = _year_range(year_start, year_end)
    sql = build_slaughter_quarterly_sql(PROJECT_ID, PECUARIA_DATASET)
    params = [
        bigquery.ScalarQueryParameter("year_start", "INT64", year_start),
        bigquery.ScalarQueryParameter("year_end", "INT64", year_end),
        bigquery.ScalarQueryParameter("quarter", "INT64", quarter),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "ibge_sidra_slaughter_1092",
        "evidence_class": "observado",
        "scope": "bovinos_mt_total_inspecao_total_trimestre",
        "temporal_warning": "Série revisionável; vintage/publicação histórica ainda não reconstruídos para uso point-in-time.",
        "filters": {"year_start": year_start, "year_end": year_end, "quarter": quarter, "limit": limit},
        "data": _query(sql, params),
    }


@router.get("/slaughter/sigsif/current")
def sigsif_current_snapshot() -> dict[str, Any]:
    sql = build_sigsif_current_sql(PROJECT_ID, PECUARIA_DATASET)
    data = _query(sql, [])
    return {
        "source_id": "mapa_sigsif_slaughter_snapshot",
        "evidence_class": "observado",
        "scope": "sif_bovinos_uf_procedencia_mt_macho_femea",
        "temporal_warning": (
            "Snapshot SIF observado na coleta; o arquivo oficial não possui período interno, "
            "portanto não representa fluxo mensal histórico."
        ),
        "data": data,
    }


@router.get("/exports/beef")
def beef_exports(
    competencia_start: str | None = None,
    competencia_end: str | None = None,
    country_code: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict[str, Any]:
    competencia_start = _competence(competencia_start, "competencia_start")
    competencia_end = _competence(competencia_end, "competencia_end")
    if competencia_start and competencia_end and competencia_start > competencia_end:
        raise HTTPException(status_code=400, detail="competencia_start não pode ser maior que competencia_end")
    country_code = _country_code(country_code)
    sql = build_beef_exports_sql(PROJECT_ID, TRADE_DATASET)
    params = [
        bigquery.ArrayQueryParameter("ncms", "STRING", list(BEEF_NCMS)),
        bigquery.ScalarQueryParameter("competencia_start", "STRING", competencia_start),
        bigquery.ScalarQueryParameter("competencia_end", "STRING", competencia_end),
        bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "mdic_comexstat_beef_mt_export_api",
        "evidence_class": "observado",
        "scope": "carne_bovina_in_natura_ncm8_corrente_0201_0202_sem_miudezas",
        "semantic_warning": "URF é unidade da Receita Federal e não porto físico.",
        "filters": {
            "competencia_start": competencia_start,
            "competencia_end": competencia_end,
            "country_code": country_code,
            "limit": limit,
        },
        "data": _query(sql, params),
    }


@router.get("/exports/beef/history")
def beef_export_history(
    year_start: int | None = Query(default=1997, ge=1997, le=2100),
    year_end: int | None = Query(default=None, ge=1997, le=2100),
    segmento: str | None = None,
    country_code: str | None = None,
    limit: int = Query(default=1000, ge=1, le=10000),
) -> dict[str, Any]:
    year_start, year_end = _year_range(year_start, year_end)
    if segmento is not None:
        segmento = segmento.strip().casefold()
        if segmento not in {"fresca_refrigerada", "congelada"}:
            raise HTTPException(status_code=400, detail="segmento deve ser fresca_refrigerada ou congelada")
    country_code = _country_code(country_code)
    sql = build_beef_export_history_sql(PROJECT_ID, TRADE_DATASET)
    params = [
        bigquery.ScalarQueryParameter("year_start", "INT64", year_start),
        bigquery.ScalarQueryParameter("year_end", "INT64", year_end),
        bigquery.ScalarQueryParameter("segmento", "STRING", segmento),
        bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return {
        "source_id": "mdic_comexstat_annual_ncm",
        "evidence_class": "observado",
        "scope": "historico_hs4_0201_0202_mato_grosso_latest_annual_snapshot",
        "semantic_warning": (
            "Histórico agregado por headings HS4 0201/0202; detalhe NCM8 não é retroprojetado. "
            "URF não equivale automaticamente a porto físico."
        ),
        "filters": {
            "year_start": year_start,
            "year_end": year_end,
            "segmento": segmento,
            "country_code": country_code,
            "limit": limit,
        },
        "data": _query(sql, params),
    }
