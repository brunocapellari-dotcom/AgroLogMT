from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

SOURCE_ID = "mapa_sigsif_slaughter_snapshot"
PACKAGE_ID = "062166e3-b515-4274-8e7d-68aadd64b820"
RESOURCE_ID = "341dc717-4716-42ab-b189-c8d7a9d2a1ba"
MALE_METRIC = "pecuaria.sigsif_abate_bovino_machos_snapshot"
FEMALE_METRIC = "pecuaria.sigsif_abate_bovino_femeas_snapshot"


def _decode(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("SIGSIF CSV sem encoding suportado")


def _key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def _integer(value: object, label: str) -> int:
    text = str(value or "").strip().replace("\xa0", "").replace(" ", "")
    if not text:
        return 0
    if re.fullmatch(r"[+-]?\d+", text):
        number = int(text)
    else:
        compact = text.replace(".", "").replace(",", "")
        if not re.fullmatch(r"[+-]?\d+", compact):
            raise ValueError(f"SIGSIF {label} inválido: {value!r}")
        number = int(compact)
    if number < 0:
        raise ValueError(f"SIGSIF {label} negativo: {value!r}")
    return number


def parse_payload(payload: bytes) -> dict[str, Any]:
    text = _decode(payload)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("SIGSIF CSV sem cabeçalho")
    normalized_headers = {_key(name): name for name in reader.fieldnames if name}

    def header(*aliases: str) -> str:
        for alias in aliases:
            original = normalized_headers.get(_key(alias))
            if original:
                return original
        raise ValueError(f"SIGSIF coluna ausente: {aliases}")

    uf_col = header("UF - PROCEDÊNCIA", "UF PROCEDÊNCIA", "UF_PROCEDENCIA")
    category_col = header("CATEGORIA")
    male_col = header("MACHO")
    female_col = header("FÊMEA", "FEMEA")

    matches: list[dict[str, Any]] = []
    for row in reader:
        uf = _key(row.get(uf_col))
        category = _key(row.get(category_col))
        if uf not in {"MT", "MATO_GROSSO"} or "BOVIN" not in category:
            continue
        matches.append(
            {
                "uf": "MT",
                "category": str(row.get(category_col) or "").strip(),
                "male": _integer(row.get(male_col), "MACHO"),
                "female": _integer(row.get(female_col), "FEMEA"),
            }
        )

    if len(matches) != 1:
        raise ValueError(
            f"SIGSIF esperado exatamente 1 registro bovino MT; encontrados={len(matches)}"
        )
    result = matches[0]
    if result["male"] + result["female"] <= 0:
        raise ValueError("SIGSIF bovinos MT sem quantidade positiva")
    return result


def build_canonical_rows(
    payload: bytes,
    *,
    source_url: str,
    data_coleta: str | None = None,
    raw_artifact_ref: str | None = None,
    collector_version: str = "mapa-sigsif-v1",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed = parse_payload(payload)
    collected = data_coleta or datetime.now(timezone.utc).isoformat()
    collected_dt = datetime.fromisoformat(collected.replace("Z", "+00:00"))
    snapshot_date = collected_dt.date().isoformat()
    snapshot_id = hashlib.sha256(payload).hexdigest()

    rows: list[dict[str, Any]] = []
    for sex, metric_id, value in (
        ("macho", MALE_METRIC, int(parsed["male"])),
        ("femea", FEMALE_METRIC, int(parsed["female"])),
    ):
        record_id = hashlib.sha256(
            f"{SOURCE_ID}|MT|bovinos|{sex}|{snapshot_id}".encode("utf-8")
        ).hexdigest()
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "record_id": record_id,
                "source_id": SOURCE_ID,
                "geo_level": "UF_PROCEDENCIA",
                "geo_id": "MT",
                "product_id": "bovinos",
                "sex": sex,
                "metric_id": metric_id,
                "value": value,
                "unit": "cabecas",
                "snapshot_date": snapshot_date,
                "data_referencia": snapshot_date,
                "data_publicacao": None,
                "data_coleta": collected,
                "data_disponibilidade": collected,
                "availability_verified": True,
                "availability_basis": "observed_at_collection_time_only",
                "point_in_time_feature_eligible": False,
                "target_role": "current_sif_crosscheck_not_historical_flow",
                "evidence_class": "observado",
                "methodology_id": "MAPA_SIGSIF_SLAUGHTER_CURRENT_SNAPSHOT",
                "raw_artifact_ref": raw_artifact_ref,
                "source_url": source_url,
                "source_hash": snapshot_id,
                "collector_version": collector_version,
                "quality_score": 1.0,
                "quality_flags": ["no_internal_reference_period"],
            }
        )

    stats = {
        "snapshot_id": snapshot_id,
        "records_read": 1,
        "records_accepted": len(rows),
        "records_rejected": 0,
        "snapshot_date": snapshot_date,
        "category": parsed["category"],
        "male": int(parsed["male"]),
        "female": int(parsed["female"]),
        "total": int(parsed["male"]) + int(parsed["female"]),
        "internal_reference_period_available": False,
        "point_in_time_feature_eligible": False,
    }
    return rows, stats
