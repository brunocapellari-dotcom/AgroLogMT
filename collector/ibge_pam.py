from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .ibge_sidra import fetch_sidra_path, parse_sidra_number

SOURCE_ID = "ibge_sidra_pam_1612"
TABLE_ID = 1612
MT_UF_CODE = 51
YIELD_VARIABLE = 112
SOY_CATEGORY = 2713
SIDRA_PATH = f"t/{TABLE_ID}/n3/{MT_UF_CODE}/v/{YIELD_VARIABLE}/p/all/c81/{SOY_CATEGORY}?formato=json"


def fetch_payload(*, timeout: int = 90) -> tuple[bytes, str]:
    return fetch_sidra_path(
        SIDRA_PATH,
        timeout=timeout,
        user_agent="AgroLogMT/0.1 (+ibge-pam)",
        error_label="SIDRA PAM",
    )


def parse_payload(payload: bytes) -> list[dict[str, Any]]:
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, list) or len(decoded) < 2:
        raise ValueError("SIDRA PAM: resposta sem linhas de dados")
    rows: list[dict[str, Any]] = []
    for raw in decoded[1:]:
        geo = str(raw.get("D1N") or "").strip()
        variable = str(raw.get("D2N") or "").strip()
        period = str(raw.get("D3N") or raw.get("D3C") or "").strip()
        product = str(raw.get("D4N") or "").strip()
        value = parse_sidra_number(raw.get("V"))
        if geo != "Mato Grosso" or "Rendimento" not in variable or "Soja" not in product or value is None:
            continue
        try:
            year = int(period)
        except ValueError:
            continue
        rows.append({
            "year": year,
            "yield_kg_ha": value,
            "geo_name": geo,
            "variable_name": variable,
            "product_name": product,
        })
    rows.sort(key=lambda item: item["year"])
    years = [row["year"] for row in rows]
    if not rows:
        raise ValueError("SIDRA PAM: nenhuma linha soja/rendimento/Mato Grosso")
    if len(set(years)) != len(years):
        raise ValueError("SIDRA PAM: anos duplicados")
    return rows


def build_canonical_rows(
    payload: bytes,
    *,
    source_url: str,
    data_coleta: str | None = None,
    raw_artifact_ref: str | None = None,
    collector_version: str = "ibge-pam-v1",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed = parse_payload(payload)
    collected = data_coleta or datetime.now(timezone.utc).isoformat()
    snapshot_id = hashlib.sha256(payload).hexdigest()
    canonical: list[dict[str, Any]] = []
    for item in parsed:
        year = int(item["year"])
        record_id = hashlib.sha256(f"{SOURCE_ID}|MT|soja|yield|{year}".encode("utf-8")).hexdigest()
        canonical.append({
            "snapshot_id": snapshot_id,
            "record_id": record_id,
            "source_id": SOURCE_ID,
            "geo_level": "UF",
            "geo_id": "MT",
            "geo_code_ibge": str(MT_UF_CODE),
            "product_id": "soja",
            "metric_id": "agro.produtividade",
            "year": year,
            "value": float(item["yield_kg_ha"]),
            "unit": "kg/ha",
            "data_referencia": f"{year}-12-31",
            "data_publicacao": None,
            "data_coleta": collected,
            "data_disponibilidade": None,
            "availability_verified": False,
            "availability_basis": "publication_timestamp_not_reconstructed",
            "point_in_time_feature_eligible": False,
            "target_role": "realized_label_not_point_in_time_feature",
            "competencia": str(year),
            "evidence_class": "observado",
            "methodology_id": "IBGE_PAM_TABLE_1612_YIELD",
            "raw_artifact_ref": raw_artifact_ref,
            "source_url": source_url,
            "source_hash": snapshot_id,
            "collector_version": collector_version,
            "quality_score": 1.0,
            "quality_flags": ["publication_time_not_reconstructed"],
        })
    stats = {
        "snapshot_id": snapshot_id,
        "records_read": len(parsed),
        "records_accepted": len(canonical),
        "records_rejected": 0,
        "year_min": min(row["year"] for row in canonical),
        "year_max": max(row["year"] for row in canonical),
        "publication_time_reconstructed": False,
        "point_in_time_feature_eligible": False,
    }
    return canonical, stats
