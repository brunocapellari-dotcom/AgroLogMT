from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any


_ID_DIMENSIONS = (
    "source_desc", "sector_desc", "group_desc", "commodity_desc", "class_desc",
    "util_practice_desc", "prodn_practice_desc", "statisticcat_desc", "unit_desc",
    "short_desc", "domain_desc", "domaincat_desc", "agg_level_desc", "state_ansi",
    "state_alpha", "state_name", "asd_code", "asd_desc", "county_ansi", "county_name",
    "region_desc", "zip_5", "watershed_code", "watershed_desc", "congr_district_code",
    "country_code", "country_name", "year", "freq_desc", "begin_code", "end_code",
    "reference_period_desc", "week_ending",
)

_PRESERVED_FIELDS = (*_ID_DIMENSIONS, "load_time")
_NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def _clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_week_ending(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_nass_value(value: Any) -> tuple[float | None, str | None, str]:
    """Preserve source value while parsing only unambiguous numeric observations."""
    raw = _clean_text(value)
    compact = raw.replace(",", "")
    if compact and _NUMERIC.fullmatch(compact):
        parsed = float(compact)
        if math.isfinite(parsed):
            return parsed, None, raw
    return None, raw or None, raw


def nass_record_id(row: dict[str, Any]) -> str:
    natural_key = {field: _clean_text(row.get(field)) for field in _ID_DIMENSIONS}
    encoded = json.dumps(natural_key, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_nass_rows(
    rows: list[dict[str, Any]],
    *,
    source_id: str,
    snapshot_id: str,
    data_coleta: str,
    source_url: str,
    source_hash: str,
    raw_artifact_ref: str | None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            raise ValueError(f"NASS row {index} is not an object")
        value_numeric, suppression_code, value_raw = parse_nass_value(raw_row.get("Value"))
        preserved = {field: _clean_text(raw_row.get(field)) for field in _PRESERVED_FIELDS}
        record = {
            "snapshot_id": snapshot_id,
            "record_id": nass_record_id(raw_row),
            "source_id": source_id,
            "evidence_class": "observado",
            "data_referencia": _parse_week_ending(raw_row.get("week_ending")),
            # Quick Stats `load_time` is source insertion metadata, not asserted as publication time.
            "data_publicacao": None,
            "data_coleta": data_coleta,
            "competencia": _clean_text(raw_row.get("week_ending")) or _clean_text(raw_row.get("year")) or None,
            "source_load_time": _clean_text(raw_row.get("load_time")) or None,
            "value_raw": value_raw,
            "value_numeric": value_numeric,
            "suppression_code": suppression_code,
            "source_url": source_url,
            "source_hash": source_hash,
            "raw_artifact_ref": raw_artifact_ref,
            **preserved,
        }
        normalized.append(record)
    return normalized


def validate_normalized_nass_rows(
    rows: list[dict[str, Any]],
    *,
    expected_source_id: str,
    expected_commodity: str | None = None,
    expected_frequency: str | None = None,
) -> dict[str, Any]:
    if not rows:
        return {"status": "empty", "rows": 0, "duplicates": 0}

    source_ids = {str(row.get("source_id")) for row in rows}
    if source_ids != {expected_source_id}:
        raise ValueError(f"NASS source_id mismatch: {sorted(source_ids)}")

    if expected_commodity:
        commodities = {str(row.get("commodity_desc", "")).upper() for row in rows}
        if commodities != {expected_commodity.upper()}:
            raise ValueError(f"NASS commodity mismatch: {sorted(commodities)}")

    if expected_frequency:
        frequencies = {str(row.get("freq_desc", "")).upper() for row in rows}
        if frequencies != {expected_frequency.upper()}:
            raise ValueError(f"NASS frequency mismatch: {sorted(frequencies)}")

    record_ids = [str(row.get("record_id", "")) for row in rows]
    if any(not value for value in record_ids):
        raise ValueError("NASS normalized row missing record_id")
    duplicates = len(record_ids) - len(set(record_ids))

    weekly_rows = [row for row in rows if str(row.get("freq_desc", "")).upper() == "WEEKLY"]
    invalid_week_dates = sum(1 for row in weekly_rows if not row.get("data_referencia"))
    if invalid_week_dates:
        raise ValueError(f"NASS weekly rows with invalid/missing week_ending: {invalid_week_dates}")

    return {
        "status": "ok",
        "rows": len(rows),
        "duplicates": duplicates,
        "numeric_values": sum(1 for row in rows if row.get("value_numeric") is not None),
        "suppressed_or_non_numeric": sum(1 for row in rows if row.get("value_numeric") is None),
    }
