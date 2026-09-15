from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SOURCE_ID = "ibge_sidra_ppm_3939"
TABLE_ID = 3939
MT_UF_CODE = 51
HERD_VARIABLE = 105
CATTLE_CATEGORY = 2670
PRIMARY_BASE = "https://apisidra.ibge.gov.br/values"
FALLBACK_BASE = "https://api.sidra.ibge.gov.br/values"


def dataset_url(*, period: str | int = "all", base_url: str = PRIMARY_BASE) -> str:
    period_text = str(period).strip()
    if period_text != "all":
        try:
            year = int(period_text)
        except ValueError as exc:
            raise ValueError("period deve ser 'all' ou um ano inteiro") from exc
        if year < 1974 or year > 2100:
            raise ValueError("ano fora do escopo da PPM moderna")
        period_text = str(year)
    geography = quote(f"in n3 {MT_UF_CODE}", safe="")
    return (
        f"{base_url}/t/{TABLE_ID}/n6/{geography}/v/{HERD_VARIABLE}"
        f"/p/{period_text}/c79/{CATTLE_CATEGORY}?formato=json"
    )


def fetch_payload(*, period: str | int = "all", timeout: int = 120) -> tuple[bytes, str]:
    errors: list[str] = []
    for base_url in (PRIMARY_BASE, FALLBACK_BASE):
        url = dataset_url(period=period, base_url=base_url)
        request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+ibge-ppm)"})
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read(), response.geturl()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    raise RuntimeError("SIDRA PPM indisponivel: " + " | ".join(errors))


def _number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"-", "...", "..", "X"}:
        return None
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") == 1:
        left, right = text.split(".", 1)
        if left.lstrip("+-").isdigit() and right.isdigit() and len(right) == 3:
            text = left + right
    elif text.count(".") > 1 and all(part.isdigit() for part in text.split(".")):
        text = text.replace(".", "")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def parse_payload(payload: bytes) -> list[dict[str, Any]]:
    decoded = json.loads(payload.decode("utf-8"))
    if not isinstance(decoded, list) or len(decoded) < 2:
        raise ValueError("SIDRA PPM: resposta sem linhas de dados")

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for raw in decoded[1:]:
        municipality_code = str(raw.get("D1C") or "").strip()
        municipality_name = str(raw.get("D1N") or "").strip()
        variable = str(raw.get("D2N") or "").strip()
        period = str(raw.get("D3N") or raw.get("D3C") or "").strip()
        herd = str(raw.get("D4N") or "").strip()
        value = _number(raw.get("V"))

        if (
            not municipality_code
            or not municipality_name
            or "efetivo" not in variable.casefold()
            or "bovino" not in herd.casefold()
            or value is None
        ):
            continue

        try:
            year = int(period)
        except ValueError:
            continue

        key = (municipality_code, year)
        if key in seen:
            raise ValueError(f"SIDRA PPM: municipio/ano duplicado: {municipality_code}/{year}")
        seen.add(key)
        rows.append(
            {
                "year": year,
                "municipality_code": municipality_code,
                "municipality_name": municipality_name,
                "cattle_head": value,
                "variable_name": variable,
                "herd_name": herd,
            }
        )

    rows.sort(key=lambda item: (item["year"], item["municipality_code"]))
    if not rows:
        raise ValueError("SIDRA PPM: nenhuma linha bovinos/efetivo/Mato Grosso")
    return rows


def build_canonical_rows(
    payload: bytes,
    *,
    source_url: str,
    data_coleta: str | None = None,
    raw_artifact_ref: str | None = None,
    collector_version: str = "ibge-ppm-v1",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed = parse_payload(payload)
    collected = data_coleta or datetime.now(timezone.utc).isoformat()
    snapshot_id = hashlib.sha256(payload).hexdigest()
    canonical: list[dict[str, Any]] = []

    for item in parsed:
        year = int(item["year"])
        municipality_code = str(item["municipality_code"])
        record_id = hashlib.sha256(
            f"{SOURCE_ID}|{municipality_code}|bovinos|herd|{year}".encode("utf-8")
        ).hexdigest()
        canonical.append(
            {
                "snapshot_id": snapshot_id,
                "record_id": record_id,
                "source_id": SOURCE_ID,
                "geo_level": "MUNICIPIO",
                "geo_id": municipality_code,
                "geo_code_ibge": municipality_code,
                "geo_name": item["municipality_name"],
                "product_id": "bovinos",
                "metric_id": "pecuaria.rebanho_bovino",
                "year": year,
                "value": float(item["cattle_head"]),
                "unit": "cabecas",
                "data_referencia": f"{year}-12-31",
                "data_publicacao": None,
                "data_coleta": collected,
                "data_disponibilidade": None,
                "availability_verified": False,
                "availability_basis": "historical_publication_timestamp_not_reconstructed",
                "point_in_time_feature_eligible": False,
                "target_role": "realized_stock_not_point_in_time_feature",
                "competencia": str(year),
                "evidence_class": "observado",
                "methodology_id": "IBGE_PPM_TABLE_3939_CATTLE_HERD",
                "raw_artifact_ref": raw_artifact_ref,
                "source_url": source_url,
                "source_hash": snapshot_id,
                "collector_version": collector_version,
                "quality_score": 1.0,
                "quality_flags": ["historical_publication_time_not_reconstructed"],
            }
        )

    years = [row["year"] for row in canonical]
    municipalities = {row["geo_code_ibge"] for row in canonical}
    stats = {
        "snapshot_id": snapshot_id,
        "records_read": len(parsed),
        "records_accepted": len(canonical),
        "records_rejected": 0,
        "municipalities": len(municipalities),
        "year_min": min(years),
        "year_max": max(years),
        "publication_time_reconstructed": False,
        "point_in_time_feature_eligible": False,
    }
    return canonical, stats
