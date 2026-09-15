from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Any

from .ibge_sidra import fetch_sidra_path, parse_sidra_number

SOURCE_ID = "ibge_sidra_slaughter_1092"
TABLE_ID = 1092
MT_UF_CODE = 51
VARIABLES = {
    "animais_abatidos": 284,
    "peso_carcacas": 285,
}
# Official SIDRA total categories used by the Quarterly Animal Slaughter Survey.
TEMPORAL_REFERENCE_CLASSIFICATION = 12716
TOTAL_QUARTER_CATEGORY = 115236
INSPECTION_CLASSIFICATION = 12529
TOTAL_INSPECTION_CATEGORY = 118225
CATTLE_HERD_CLASSIFICATION = 18
TOTAL_CATTLE_CATEGORY = 992


def _validate_period(period: str | int) -> str:
    text = str(period).strip()
    if text == "all":
        return text
    if not re.fullmatch(r"\d{6}", text):
        raise ValueError("period deve ser 'all' ou trimestre SIDRA YYYYQQ")
    year = int(text[:4])
    quarter = int(text[4:])
    if year < 1997 or year > 2100 or quarter not in {1, 2, 3, 4}:
        raise ValueError("trimestre fora do escopo da Pesquisa Trimestral do Abate")
    return text


def dataset_path(*, period: str | int = "all") -> str:
    period_text = _validate_period(period)
    variables = ",".join(str(code) for code in VARIABLES.values())
    return (
        f"t/{TABLE_ID}/n3/{MT_UF_CODE}/v/{variables}/p/{period_text}"
        f"/c{TEMPORAL_REFERENCE_CLASSIFICATION}/{TOTAL_QUARTER_CATEGORY}"
        f"/c{INSPECTION_CLASSIFICATION}/{TOTAL_INSPECTION_CATEGORY}"
        f"/c{CATTLE_HERD_CLASSIFICATION}/{TOTAL_CATTLE_CATEGORY}?formato=json"
    )


def fetch_payload(*, period: str | int = "all", timeout: int = 120) -> tuple[bytes, str]:
    return fetch_sidra_path(
        dataset_path(period=period),
        timeout=timeout,
        user_agent="AgroLogMT/0.1 (+ibge-slaughter)",
        error_label="SIDRA Abate",
    )


def _dimension(header: dict[str, Any], *needles: str) -> tuple[str, str]:
    wanted = tuple(needle.casefold() for needle in needles)
    for key, value in header.items():
        if not (key.startswith("D") and key.endswith("N")):
            continue
        label = str(value or "").casefold()
        if any(needle in label for needle in wanted):
            return key, f"{key[:-1]}C"
    raise ValueError(f"SIDRA Abate: dimensão ausente: {needles}")


def _quarter(code: object, label: object) -> tuple[int, int]:
    code_text = str(code or "").strip()
    match = re.fullmatch(r"(\d{4})0?([1-4])", code_text)
    if match:
        return int(match.group(1)), int(match.group(2))

    label_text = str(label or "").strip().casefold()
    match = re.search(r"([1-4])\s*[ºo°]?\s*trimestre[^0-9]*(\d{4})", label_text)
    if match:
        return int(match.group(2)), int(match.group(1))
    match = re.search(r"(\d{4})[^0-9]*([1-4])\s*[ºo°]?\s*trimestre", label_text)
    if match:
        return int(match.group(1)), int(match.group(2))
    raise ValueError(f"SIDRA Abate: trimestre inválido: code={code_text!r} label={label_text!r}")


def _metric(variable_name: str) -> tuple[str, str] | None:
    normalized = variable_name.casefold()
    if "animais abatidos" in normalized:
        return "pecuaria.abate_bovino_cabecas", "cabecas"
    if "peso total das carca" in normalized:
        return "pecuaria.abate_bovino_peso_carcaca", "kg"
    return None


def _quarter_end(year: int, quarter: int) -> str:
    month = quarter * 3
    return date(year, month, monthrange(year, month)[1]).isoformat()


def parse_payload(payload: bytes) -> list[dict[str, Any]]:
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, list) or len(decoded) < 2 or not isinstance(decoded[0], dict):
        raise ValueError("SIDRA Abate: resposta sem linhas de dados")

    header = decoded[0]
    geo_name_key, geo_code_key = _dimension(header, "unidade da federação")
    variable_name_key, variable_code_key = _dimension(header, "variável", "variavel")
    period_name_key, period_code_key = _dimension(header, "trimestre")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    for raw in decoded[1:]:
        if not isinstance(raw, dict):
            continue
        geo_name = str(raw.get(geo_name_key) or "").strip()
        geo_code = str(raw.get(geo_code_key) or "").strip()
        if geo_name.casefold() != "mato grosso" or geo_code not in {str(MT_UF_CODE), "MT"}:
            continue

        variable_name = str(raw.get(variable_name_key) or "").strip()
        variable_code = str(raw.get(variable_code_key) or "").strip()
        metric = _metric(variable_name)
        value = parse_sidra_number(raw.get("V"))
        if metric is None or value is None:
            continue

        year, quarter = _quarter(raw.get(period_code_key), raw.get(period_name_key))
        metric_id, unit = metric
        key = (year, quarter, metric_id)
        if key in seen:
            raise ValueError(f"SIDRA Abate: trimestre/métrica duplicado: {key}")
        seen.add(key)
        rows.append(
            {
                "year": year,
                "quarter": quarter,
                "period_code": f"{year}{quarter:02d}",
                "geo_code_ibge": str(MT_UF_CODE),
                "geo_name": geo_name,
                "variable_code": variable_code,
                "variable_name": variable_name,
                "metric_id": metric_id,
                "unit": unit,
                "value": float(value),
            }
        )

    rows.sort(key=lambda row: (row["year"], row["quarter"], row["metric_id"]))
    if not rows:
        raise ValueError("SIDRA Abate: nenhuma observação bovina de Mato Grosso")
    return rows


def build_canonical_rows(
    payload: bytes,
    *,
    source_url: str,
    data_coleta: str | None = None,
    raw_artifact_ref: str | None = None,
    collector_version: str = "ibge-slaughter-v1",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed = parse_payload(payload)
    collected = data_coleta or datetime.now(timezone.utc).isoformat()
    snapshot_id = hashlib.sha256(payload).hexdigest()
    canonical: list[dict[str, Any]] = []
    for item in parsed:
        year = int(item["year"])
        quarter = int(item["quarter"])
        metric_id = str(item["metric_id"])
        record_id = hashlib.sha256(
            f"{SOURCE_ID}|MT|bovinos|{metric_id}|{year}|Q{quarter}".encode("utf-8")
        ).hexdigest()
        canonical.append(
            {
                "snapshot_id": snapshot_id,
                "record_id": record_id,
                "source_id": SOURCE_ID,
                "geo_level": "UF",
                "geo_id": "MT",
                "geo_code_ibge": str(MT_UF_CODE),
                "geo_name": "Mato Grosso",
                "product_id": "bovinos",
                "metric_id": metric_id,
                "year": year,
                "quarter": quarter,
                "value": float(item["value"]),
                "unit": item["unit"],
                "data_referencia": _quarter_end(year, quarter),
                "data_publicacao": None,
                "data_coleta": collected,
                "data_disponibilidade": None,
                "availability_verified": False,
                "availability_basis": "historical_release_timestamp_not_reconstructed",
                "point_in_time_feature_eligible": False,
                "target_role": "realized_flow_not_point_in_time_feature",
                "competencia": f"{year}-Q{quarter}",
                "evidence_class": "observado",
                "methodology_id": "IBGE_QUARTERLY_SLAUGHTER_TABLE_1092_TOTAL_CATTLE",
                "raw_artifact_ref": raw_artifact_ref,
                "source_url": source_url,
                "source_hash": snapshot_id,
                "collector_version": collector_version,
                "quality_score": 1.0,
                "quality_flags": ["historical_release_time_not_reconstructed"],
            }
        )

    years = [int(row["year"]) for row in canonical]
    periods = {(int(row["year"]), int(row["quarter"])) for row in canonical}
    metrics = {str(row["metric_id"]) for row in canonical}
    stats = {
        "snapshot_id": snapshot_id,
        "records_read": len(parsed),
        "records_accepted": len(canonical),
        "records_rejected": 0,
        "quarters": len(periods),
        "metrics": sorted(metrics),
        "year_min": min(years),
        "year_max": max(years),
        "publication_time_reconstructed": False,
        "point_in_time_feature_eligible": False,
    }
    return canonical, stats
