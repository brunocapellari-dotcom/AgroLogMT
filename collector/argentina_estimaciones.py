from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .transport_security import validate_https_url

SOURCE_ID = "sagyp_argentina"
CKAN_BASE = "https://datos.magyp.gob.ar/api/3/action"
PACKAGE_ID = "estimaciones-agricolas"
RESOURCE_ID = "95d066e6-8a0f-4a80-b59d-6f28f88eacd5"
ALLOWED_HOSTS = {"datos.magyp.gob.ar", "www.datos.gob.ar", "datos.gob.ar"}


@dataclass(frozen=True)
class ArgentinaCropRecord:
    source_id: str
    crop: str
    crop_id: str
    year: int | None
    season: str
    province: str
    province_id: str | None
    department: str
    department_id: str | None
    planted_area_ha: float | None
    harvested_area_ha: float | None
    production_t: float | None
    yield_kg_ha: float | None
    evidence_class: str = "ESTIMADO"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(" ", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def canonical_crop(value: str) -> str:
    folded = _fold(value)
    aliases = {
        "soja": "soja",
        "maiz": "milho",
        "maiz_total": "milho",
        "trigo": "trigo",
        "trigo_pan": "trigo",
        "algodon": "algodao",
    }
    return aliases.get(folded, folded or "desconhecido")


def parse_estimaciones_csv(payload: bytes) -> list[ArgentinaCropRecord]:
    text = payload.decode("utf-8-sig", errors="strict")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    out: list[ArgentinaCropRecord] = []
    for raw in reader:
        row = {_fold(k): v for k, v in raw.items() if k is not None}
        crop = str(row.get("cultivo") or "").strip()
        season = str(row.get("campania") or row.get("campana") or "").strip()
        if not crop or not season:
            continue
        province = str(row.get("provincia") or "").strip()
        department = str(row.get("departamento") or "").strip()
        out.append(ArgentinaCropRecord(
            source_id=SOURCE_ID,
            crop=crop,
            crop_id=canonical_crop(crop),
            year=_integer(row.get("anio")),
            season=season,
            province=province,
            province_id=(str(row.get("provincia_id")).strip() if row.get("provincia_id") not in (None, "") else None),
            department=department,
            department_id=(str(row.get("departamento_id")).strip() if row.get("departamento_id") not in (None, "") else None),
            planted_area_ha=_number(row.get("superficie_sembrada_ha")),
            harvested_area_ha=_number(row.get("superficie_cosechada_ha")),
            production_t=_number(row.get("produccion_tm")),
            yield_kg_ha=_number(row.get("rendimiento_kgxha")),
        ))
    if not out:
        raise ValueError("Argentina estimaciones CSV produced no valid crop rows")
    return out


def package_url() -> str:
    return f"{CKAN_BASE}/package_show?{urlencode({'id': PACKAGE_ID})}"


def fetch_json(url: str, *, timeout: int = 30) -> dict[str, Any]:
    validate_https_url(url, allowed_hosts=ALLOWED_HOSTS)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "AgroLogMT/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - HTTPS + allowlist validated.
        validate_https_url(response.geturl(), allowed_hosts=ALLOWED_HOSTS)
        return json.loads(response.read().decode("utf-8"))


def discover_csv_url(package_payload: dict[str, Any], *, resource_id: str = RESOURCE_ID) -> str:
    result = package_payload.get("result") if isinstance(package_payload, dict) else None
    resources = result.get("resources", []) if isinstance(result, dict) else []
    for resource in resources:
        if str(resource.get("id")) != resource_id:
            continue
        url = str(resource.get("url") or "").strip()
        fmt = str(resource.get("format") or "").lower()
        if not url:
            raise ValueError("Argentina official resource has no download URL")
        if fmt and "csv" not in fmt:
            raise ValueError(f"Argentina resource format is not CSV: {fmt}")
        validate_https_url(url, allowed_hosts=ALLOWED_HOSTS)
        return url
    raise ValueError(f"Argentina resource not found: {resource_id}")


def fetch_official_csv(*, timeout: int = 60) -> tuple[bytes, str]:
    metadata = fetch_json(package_url(), timeout=timeout)
    url = discover_csv_url(metadata)
    request = Request(url, headers={"Accept": "text/csv,*/*", "User-Agent": "AgroLogMT/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - HTTPS + allowlist validated.
        validate_https_url(response.geturl(), allowed_hosts=ALLOWED_HOSTS)
        payload = response.read()
    return payload, url


def snapshot_metadata(payload: bytes, *, collected_at: datetime | None = None) -> dict[str, str]:
    collected = (collected_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "source_id": SOURCE_ID,
        "snapshot_id": f"argentina_estimaciones:{digest[:24]}",
        "source_hash": digest,
        "data_coleta": collected.isoformat(),
    }
