from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, TYPE_CHECKING

from .conab_safra import ConabSafraRecord, parse_conab_safra_workbook
from .models import SourceSpec
from .orchestrator import COLLECTOR_VERSION, CollectorEngine

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime

PARSER_VERSION = "conab_safra_v1"
METHODOLOGY_ID = "conab_safra_graos_monthly_v1"

CONAB_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "source_id": "VARCHAR NOT NULL",
    "geo_level": "VARCHAR NOT NULL",
    "geo_id": "VARCHAR NOT NULL",
    "produto_origem": "VARCHAR NOT NULL",
    "product_id": "VARCHAR NOT NULL",
    "safra": "VARCHAR NOT NULL",
    "vintage_position": "VARCHAR NOT NULL",
    "area_mil_ha": "DOUBLE NOT NULL",
    "produtividade_kg_ha": "DOUBLE NOT NULL",
    "producao_mil_t": "DOUBLE NOT NULL",
    "area_var_pct": "DOUBLE",
    "produtividade_var_pct": "DOUBLE",
    "producao_var_pct": "DOUBLE",
    "identity_error_mil_t": "DOUBLE",
    "identity_error_pct": "DOUBLE",
    "data_referencia": "DATE NOT NULL",
    "data_publicacao": "TIMESTAMP NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "data_disponibilidade": "TIMESTAMP",
    "availability_verified": "BOOLEAN NOT NULL",
    "availability_basis": "VARCHAR",
    "competencia": "VARCHAR NOT NULL",
    "evidence_class": "VARCHAR NOT NULL",
    "methodology_id": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
    "source_url": "VARCHAR",
    "source_hash": "VARCHAR NOT NULL",
    "collector_version": "VARCHAR",
    "parser_version": "VARCHAR",
    "quality_score": "DOUBLE",
    "quality_flags_json": "VARCHAR",
    "source_sheet": "VARCHAR",
    "source_row": "BIGINT",
}
CONAB_ORDER = list(CONAB_COLUMNS)


def _iso_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _publication_dt(last_modified: str | None, data_coleta: str) -> datetime:
    if last_modified:
        try:
            parsed = parsedate_to_datetime(last_modified)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return _iso_dt(data_coleta)


def canonical_conab_row(
    record: ConabSafraRecord,
    *,
    snapshot_id: str,
    data_coleta: str,
    raw_artifact_ref: str | None,
    observed_url: str | None,
    publication: datetime,
) -> dict[str, Any]:
    identity = "|".join((
        snapshot_id,
        record.geo_level,
        record.geo_id,
        record.product_id,
        record.safra,
        record.vintage_position,
    ))
    row = record.to_dict()
    row.pop("quality_flags", None)
    row.update({
        "snapshot_id": snapshot_id,
        "record_id": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "data_referencia": publication.date().isoformat(),
        "data_publicacao": publication.isoformat(),
        "data_coleta": data_coleta,
        "data_disponibilidade": None,
        "availability_verified": False,
        "availability_basis": "runtime_collection",
        "competencia": publication.strftime("%Y-%m"),
        "evidence_class": "estimado",
        "methodology_id": METHODOLOGY_ID,
        "raw_artifact_ref": raw_artifact_ref,
        "source_url": observed_url,
        "source_hash": snapshot_id,
        "collector_version": COLLECTOR_VERSION,
        "parser_version": PARSER_VERSION,
        "quality_flags_json": json.dumps(list(record.quality_flags), ensure_ascii=False),
    })
    return row


def build_conab_rows(
    payload: bytes,
    *,
    snapshot_id: str,
    data_coleta: str,
    raw_artifact_ref: str | None,
    observed_url: str | None,
    last_modified: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    publication = _publication_dt(last_modified, data_coleta)
    records = parse_conab_safra_workbook(payload)
    rows = [
        canonical_conab_row(
            record,
            snapshot_id=snapshot_id,
            data_coleta=data_coleta,
            raw_artifact_ref=raw_artifact_ref,
            observed_url=observed_url,
            publication=publication,
        )
        for record in records
    ]
    current = [record for record in records if record.vintage_position == "current"]
    flagged = [record for record in current if record.quality_flags]
    stats = {
        "records_read": len(records),
        "records_accepted": len(rows),
        "records_rejected": 0,
        "current_records": len(current),
        "current_quality_flagged": len(flagged),
        "geo_ids": len({record.geo_id for record in records}),
        "products": len({record.product_id for record in current}),
        "data_publicacao_basis": "http_last_modified" if last_modified else "data_coleta_fallback",
    }
    return rows, stats


def persist_conab_rows(
    runtime: "ZeroCostRuntime",
    rows: list[dict[str, Any]],
    *,
    snapshot_id: str,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("CONAB Safra local loader recusou lote vazio")
    unique = {str(row["record_id"]): row for row in rows}
    canonical = list(unique.values())
    runtime.analytics.ensure_table("agro", "conab_safra_graos", CONAB_COLUMNS)
    existing = int(runtime.analytics.scalar(
        "SELECT COUNT(*) FROM agro.conab_safra_graos WHERE snapshot_id=?",
        [snapshot_id],
    ) or 0)
    if existing and existing != len(canonical):
        raise RuntimeError(
            f"Tie-out CONAB Safra local falhou: snapshot={snapshot_id} esperado={len(canonical)} persistido={existing}"
        )
    inserted = 0 if existing else runtime.analytics.insert_rows(
        "agro", "conab_safra_graos", canonical, columns=CONAB_ORDER
    )
    parquet = runtime.analytics.export_table_parquet("agro", "conab_safra_graos")
    return {
        "table": "agro.conab_safra_graos",
        "snapshot_id": snapshot_id,
        "records_input": len(rows),
        "records_unique": len(canonical),
        "inserted": inserted,
        "records_existing": existing,
        "parquet": str(parquet),
    }


def run_conab_source(runtime: "ZeroCostRuntime", spec: SourceSpec) -> tuple[int, dict[str, Any]]:
    outcome = CollectorEngine(store=runtime.raw).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"status": "source_error", "acquisition": manifest.to_dict()}
    try:
        rows, stats = build_conab_rows(
            outcome.payload,
            snapshot_id=manifest.sha256,
            data_coleta=manifest.data_coleta,
            raw_artifact_ref=manifest.raw_artifact_ref,
            observed_url=manifest.observed_url,
            last_modified=manifest.last_modified,
        )
        if not rows:
            raise RuntimeError("CONAB Safra: parser retornou lote vazio")
        if stats["current_quality_flagged"]:
            raise RuntimeError(
                "CONAB Safra: registros current com flags materiais de identidade "
                f"({stats['current_quality_flagged']})"
            )
        load = persist_conab_rows(runtime, rows, snapshot_id=manifest.sha256)
        return 0, {
            "status": "ok",
            "acquisition": manifest.to_dict(),
            "parsing": stats,
            "load": load,
        }
    except Exception as exc:
        return 2, {
            "status": "blocked_by_quality_gate",
            "acquisition": manifest.to_dict(),
            "error": f"{type(exc).__name__}: {exc}",
        }
