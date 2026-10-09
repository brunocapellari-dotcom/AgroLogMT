from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime


ALLOWED_USAGE_RIGHTS = {
    "PUBLIC_OPEN",
    "LICENSED",
    "INTERNAL_AUTHORIZED",
    "USER_AUTHORIZED",
}
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "private_key",
    "client_secret",
    "api_key",
    "apikey",
    "credential",
)

MARKET_COLUMNS = {
    "record_id": "VARCHAR NOT NULL",
    "series_key": "VARCHAR NOT NULL",
    "source_id": "VARCHAR NOT NULL",
    "source_name": "VARCHAR NOT NULL",
    "usage_rights": "VARCHAR NOT NULL",
    "authorization_basis": "VARCHAR NOT NULL",
    "product_id": "VARCHAR NOT NULL",
    "produto": "VARCHAR NOT NULL",
    "metric_name": "VARCHAR NOT NULL",
    "local": "VARCHAR NOT NULL",
    "valor": "DOUBLE NOT NULL",
    "unidade_origem": "VARCHAR NOT NULL",
    "unidade_canonica": "VARCHAR",
    "data_referencia": "DATE NOT NULL",
    "data_publicacao": "TIMESTAMP",
    "data_coleta": "TIMESTAMP NOT NULL",
    "competencia": "VARCHAR NOT NULL",
    "evidence_class": "VARCHAR NOT NULL",
    "provenance_json": "VARCHAR NOT NULL",
}
MARKET_ORDER = list(MARKET_COLUMNS)


@dataclass(frozen=True)
class MarketAuthorization:
    source_id: str
    source_name: str
    usage_rights: str
    authorization_basis: str

    def validate(self) -> None:
        if not self.source_id.strip() or not self.source_name.strip():
            raise ValueError("source_id and source_name are required")
        rights = self.usage_rights.strip().upper()
        if rights not in ALLOWED_USAGE_RIGHTS:
            raise ValueError(
                "usage_rights must be one of: " + ", ".join(sorted(ALLOWED_USAGE_RIGHTS))
            )
        if not self.authorization_basis.strip():
            raise ValueError("authorization_basis is required; do not assume reuse rights")


def _hash(parts: Iterable[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _required_text(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"market reference missing required field: {key}")
    return value


def _optional_text(row: dict[str, Any], key: str) -> str | None:
    value = str(row.get(key) or "").strip()
    return value or None


def _check_sensitive(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in SENSITIVE_KEY_PARTS):
                if child not in (None, "", [], {}):
                    raise ValueError(f"sensitive field forbidden in market import: {path}.{key}")
            _check_sensitive(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_sensitive(child, f"{path}[{index}]")


def _parse_date(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid {field}: {text!r}") from exc


def _parse_optional_datetime(value: Any, *, field: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def normalize_market_reference(
    row: dict[str, Any],
    *,
    authorization: MarketAuthorization,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    authorization.validate()
    _check_sensitive(row)
    product_id = _required_text(row, "product_id").lower()
    produto = _optional_text(row, "produto") or product_id
    metric_name = _required_text(row, "metric_name")
    local = _required_text(row, "local")
    unit_origin = _required_text(row, "unidade_origem")
    unit_canonical = _optional_text(row, "unidade_canonica") or unit_origin
    reference_date = _parse_date(row.get("data_referencia"), field="data_referencia")
    publication = _parse_optional_datetime(row.get("data_publicacao"), field="data_publicacao")
    collected = (collected_at or datetime.now(timezone.utc)).astimezone(timezone.utc)

    try:
        value = float(str(row["valor"]).replace(",", "."))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("valor must be numeric") from exc

    series_key = _hash([
        authorization.source_id,
        product_id,
        metric_name.strip().lower(),
        local.strip().lower(),
        unit_canonical.strip().lower(),
    ])
    record_id = _hash([
        series_key,
        reference_date,
        f"{value:.8f}",
        publication or "",
    ])
    provenance = row.get("provenance") or {}
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")

    return {
        "record_id": record_id,
        "series_key": series_key,
        "source_id": authorization.source_id.strip(),
        "source_name": authorization.source_name.strip(),
        "usage_rights": authorization.usage_rights.strip().upper(),
        "authorization_basis": authorization.authorization_basis.strip(),
        "product_id": product_id,
        "produto": produto,
        "metric_name": metric_name,
        "local": local,
        "valor": value,
        "unidade_origem": unit_origin,
        "unidade_canonica": unit_canonical,
        "data_referencia": reference_date,
        "data_publicacao": publication,
        "data_coleta": collected.isoformat(),
        "competencia": reference_date[:7],
        "evidence_class": "OBSERVADO",
        "provenance_json": json.dumps(provenance, ensure_ascii=False, sort_keys=True),
    }


def persist_market_references(
    runtime: "ZeroCostRuntime",
    records: list[dict[str, Any]],
    *,
    authorization: MarketAuthorization,
    collected_at: datetime | None = None,
) -> dict[str, Any]:
    if not records:
        raise ValueError("ZERO_COST market import cannot be empty")
    normalized = [
        normalize_market_reference(
            row,
            authorization=authorization,
            collected_at=collected_at,
        )
        for row in records
    ]
    runtime.analytics.ensure_table("mercado", "market_reference", MARKET_COLUMNS)
    inserted = 0
    duplicates = 0
    for row in normalized:
        exists = runtime.analytics.scalar(
            "SELECT COUNT(*) FROM mercado.market_reference WHERE record_id=?",
            [row["record_id"]],
        )
        if exists:
            duplicates += 1
            continue
        inserted += runtime.analytics.insert_rows(
            "mercado", "market_reference", [row], columns=MARKET_ORDER
        )
    parquet = runtime.analytics.export_table_parquet("mercado", "market_reference")
    return {
        "source_id": authorization.source_id,
        "usage_rights": authorization.usage_rights.upper(),
        "records_input": len(records),
        "records_inserted": inserted,
        "duplicates": duplicates,
        "parquet": str(parquet),
    }


def load_market_input(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    text = source.read_text(encoding="utf-8")
    if suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            rows = payload["records"]
        else:
            raise ValueError("market JSON must be an array or an object with records[]")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("all market records must be objects")
    return [dict(row) for row in rows]
