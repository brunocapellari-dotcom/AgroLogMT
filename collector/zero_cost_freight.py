from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime


PUBLICATION_COLUMNS = {
    "publication_id": "VARCHAR NOT NULL",
    "source_provider": "VARCHAR NOT NULL",
    "carrier_id": "VARCHAR NOT NULL",
    "carrier_name": "VARCHAR NOT NULL",
    "data_publicacao": "TIMESTAMP NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "source_reference_hash": "VARCHAR",
    "provenance_json": "VARCHAR NOT NULL",
}
PUBLICATION_ORDER = list(PUBLICATION_COLUMNS)

FREIGHT_COLUMNS = {
    "record_id": "VARCHAR NOT NULL",
    "publication_id": "VARCHAR NOT NULL",
    "source_provider": "VARCHAR NOT NULL",
    "carrier_id": "VARCHAR NOT NULL",
    "carrier_name": "VARCHAR NOT NULL",
    "municipality_id": "VARCHAR",
    "municipality_name": "VARCHAR NOT NULL",
    "pickup_entity_id": "VARCHAR NOT NULL",
    "pickup_name": "VARCHAR NOT NULL",
    "destination_id": "VARCHAR",
    "destination_name": "VARCHAR NOT NULL",
    "product_id": "VARCHAR NOT NULL",
    "freight_announced_brl_per_t": "DOUBLE NOT NULL",
    "data_referencia": "DATE NOT NULL",
    "data_publicacao": "TIMESTAMP NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "competencia": "VARCHAR NOT NULL",
    "evidence_class": "VARCHAR NOT NULL",
    "evidence_subtype": "VARCHAR NOT NULL",
    "negotiated_status": "VARCHAR NOT NULL",
    "executed_status": "VARCHAR NOT NULL",
    "content_fingerprint": "VARCHAR NOT NULL",
    "provenance_json": "VARCHAR NOT NULL",
}
FREIGHT_ORDER = list(FREIGHT_COLUMNS)

FORBIDDEN_INPUT_KEYS = {
    "phone",
    "phone_number",
    "sender_phone",
    "raw_contact",
    "contact_phone",
}


def _required_text(row: dict[str, Any], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ValueError(f"freight record missing required field: {key}")
    return value


def _optional_text(row: dict[str, Any], key: str) -> str | None:
    value = str(row.get(key) or "").strip()
    return value or None


def _dt(value: Any, *, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash(parts: Iterable[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _check_sensitive_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_INPUT_KEYS and child not in (None, "", [], {}):
                raise ValueError(f"sensitive contact field is forbidden in ZERO_COST freight input: {path}.{key}")
            _check_sensitive_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_sensitive_keys(child, f"{path}[{index}]")


def normalize_freight_record(row: dict[str, Any], *, collected_at: datetime | None = None) -> dict[str, Any]:
    _check_sensitive_keys(row)

    publication_id = _required_text(row, "publication_id")
    source_provider = _required_text(row, "source_provider")
    carrier_name = _required_text(row, "carrier_name")
    carrier_id = _optional_text(row, "carrier_id") or _hash(["carrier", carrier_name.upper()])

    municipality_name = _required_text(row, "municipality_name")
    municipality_id = _optional_text(row, "municipality_id")
    pickup_name = _required_text(row, "pickup_name")
    pickup_entity_id = _optional_text(row, "pickup_entity_id") or _hash(
        ["pickup", municipality_id or municipality_name.upper(), pickup_name.upper()]
    )

    destination_name = _required_text(row, "destination_name")
    destination_id = _optional_text(row, "destination_id")
    product_id = _required_text(row, "product_id").lower()

    try:
        freight = float(row["freight_announced_brl_per_t"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("freight_announced_brl_per_t must be numeric") from exc
    if freight < 0:
        raise ValueError("freight_announced_brl_per_t cannot be negative")

    published = _dt(row.get("data_publicacao"), field="data_publicacao")
    collected = collected_at or _dt(row.get("data_coleta") or datetime.now(timezone.utc), field="data_coleta")
    if collected < published:
        raise ValueError("data_coleta cannot precede data_publicacao")

    reference_date = str(row.get("data_referencia") or published.date().isoformat())[:10]
    try:
        datetime.fromisoformat(reference_date)
    except ValueError as exc:
        raise ValueError("invalid data_referencia") from exc

    fingerprint = _hash([
        reference_date,
        carrier_id,
        pickup_entity_id,
        destination_id or destination_name.upper(),
        product_id,
        f"{freight:.4f}",
    ])
    record_id = _optional_text(row, "record_id") or fingerprint

    provenance = row.get("provenance") or {}
    if not isinstance(provenance, dict):
        raise ValueError("provenance must be an object")

    return {
        "record_id": record_id,
        "publication_id": publication_id,
        "source_provider": source_provider,
        "carrier_id": carrier_id,
        "carrier_name": carrier_name,
        "municipality_id": municipality_id,
        "municipality_name": municipality_name,
        "pickup_entity_id": pickup_entity_id,
        "pickup_name": pickup_name,
        "destination_id": destination_id,
        "destination_name": destination_name,
        "product_id": product_id,
        "freight_announced_brl_per_t": freight,
        "data_referencia": reference_date,
        "data_publicacao": published.isoformat(),
        "data_coleta": collected.isoformat(),
        "competencia": f"{published.year:04d}-{published.month:02d}",
        "evidence_class": "OBSERVADO",
        "evidence_subtype": "FRETE_ANUNCIADO",
        "negotiated_status": "DESCONHECIDO",
        "executed_status": "DESCONHECIDO",
        "content_fingerprint": fingerprint,
        "provenance_json": json.dumps(provenance, ensure_ascii=False, sort_keys=True),
    }


def _publication_row(row: dict[str, Any], *, provenance_json: str) -> dict[str, Any]:
    source_reference = _optional_text(row, "source_reference")
    return {
        "publication_id": row["publication_id"],
        "source_provider": row["source_provider"],
        "carrier_id": row["carrier_id"],
        "carrier_name": row["carrier_name"],
        "data_publicacao": row["data_publicacao"],
        "data_coleta": row["data_coleta"],
        "source_reference_hash": _hash([source_reference]) if source_reference else None,
        "provenance_json": provenance_json,
    }


def persist_freight_records(runtime: "ZeroCostRuntime", records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        raise ValueError("ZERO_COST freight import cannot be empty")

    normalized = [normalize_freight_record(row) for row in records]
    runtime.analytics.ensure_table("logistica", "freight_publications", PUBLICATION_COLUMNS)
    runtime.analytics.ensure_table("logistica", "freight_announcements", FREIGHT_COLUMNS)

    publications_inserted = 0
    records_inserted = 0
    republications_deduplicated = 0

    for original, row in zip(records, normalized):
        publication_exists = runtime.analytics.scalar(
            "SELECT COUNT(*) FROM logistica.freight_publications WHERE publication_id=?",
            [row["publication_id"]],
        )
        if not publication_exists:
            publication = _publication_row(row, provenance_json=row["provenance_json"])
            publication["source_reference_hash"] = (
                _hash([str(original.get("source_reference"))])
                if original.get("source_reference")
                else None
            )
            publications_inserted += runtime.analytics.insert_rows(
                "logistica", "freight_publications", [publication], columns=PUBLICATION_ORDER
            )

        duplicate = runtime.analytics.scalar(
            """
            SELECT COUNT(*) FROM logistica.freight_announcements
            WHERE content_fingerprint=?
            """,
            [row["content_fingerprint"]],
        )
        if duplicate:
            republications_deduplicated += 1
            continue
        records_inserted += runtime.analytics.insert_rows(
            "logistica", "freight_announcements", [row], columns=FREIGHT_ORDER
        )

    publications_parquet = runtime.analytics.export_table_parquet(
        "logistica", "freight_publications"
    )
    records_parquet = runtime.analytics.export_table_parquet(
        "logistica", "freight_announcements"
    )
    return {
        "publications_input": len({row["publication_id"] for row in normalized}),
        "publications_inserted": publications_inserted,
        "records_input": len(records),
        "records_inserted": records_inserted,
        "republications_deduplicated": republications_deduplicated,
        "publications_parquet": str(publications_parquet),
        "records_parquet": str(records_parquet),
    }


def load_freight_input(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
            rows = payload["records"]
        else:
            raise ValueError("freight JSON must be an array or an object with records[]")
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("all freight records must be objects")
    return [dict(row) for row in rows]
