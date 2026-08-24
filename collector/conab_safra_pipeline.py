from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from .cloud_store import DriveBigQueryStore
from .conab_safra import parse_conab_safra_workbook
from .conab_safra_bigquery import ConabSafraBigQueryLoader
from .models import SourceSpec
from .orchestrator import COLLECTOR_VERSION, CollectorEngine

PARSER_VERSION = "conab_safra_v1"
METHODOLOGY_ID = "conab_safra_graos_monthly_v1"


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


def build_canonical_rows(
    payload: bytes,
    *,
    snapshot_id: str,
    data_coleta: str,
    raw_artifact_ref: str | None,
    observed_url: str | None,
    last_modified: str | None,
    publication_override: str | datetime | None = None,
    availability_verified: bool = False,
    availability_basis: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if availability_verified and publication_override is None:
        raise ValueError("availability_verified exige publication_override explícito")
    publication = _iso_dt(publication_override) if publication_override is not None else _publication_dt(last_modified, data_coleta)
    reference_date = publication.date().isoformat()
    competencia = publication.strftime("%Y-%m")
    records = parse_conab_safra_workbook(payload)
    rows: list[dict[str, Any]] = []
    for record in records:
        identity = "|".join((snapshot_id, record.geo_level, record.geo_id, record.product_id, record.safra, record.vintage_position))
        record_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        row = record.to_dict()
        row.update({
            "snapshot_id": snapshot_id,
            "record_id": record_id,
            "data_referencia": reference_date,
            "data_publicacao": publication.isoformat(),
            "data_coleta": data_coleta,
            "data_disponibilidade": publication.isoformat() if availability_verified else None,
            "availability_verified": availability_verified,
            "availability_basis": availability_basis if availability_verified else "runtime_collection",
            "competencia": competencia,
            "evidence_class": "estimado",
            "methodology_id": METHODOLOGY_ID,
            "raw_artifact_ref": raw_artifact_ref,
            "source_url": observed_url,
            "source_hash": snapshot_id,
            "collector_version": COLLECTOR_VERSION,
            "parser_version": PARSER_VERSION,
        })
        rows.append(row)

    current = [r for r in records if r.vintage_position == "current"]
    flagged = [r for r in current if r.quality_flags]
    stats = {
        "records_read": len(records),
        "records_accepted": len(rows),
        "records_rejected": 0,
        "current_records": len(current),
        "current_quality_flagged": len(flagged),
        "geo_ids": len({r.geo_id for r in records}),
        "products": len({r.product_id for r in current}),
        "data_publicacao_basis": "historical_verified_override" if publication_override is not None else ("http_last_modified" if last_modified else "data_coleta_fallback"),
        "availability_verified": availability_verified,
        "availability_basis": availability_basis if availability_verified else "runtime_collection",
    }
    return rows, stats


def run_conab_safra_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    outcome = CollectorEngine(store=store).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"acquisition": manifest.to_dict()}

    rows, stats = build_canonical_rows(
        outcome.payload,
        snapshot_id=manifest.sha256,
        data_coleta=manifest.data_coleta,
        raw_artifact_ref=manifest.raw_artifact_ref,
        observed_url=manifest.observed_url,
        last_modified=manifest.last_modified,
    )
    if not rows:
        return 2, {"status": "blocked_by_quality_gate", "reason": "empty_parse", "acquisition": manifest.to_dict(), "parsing": stats}
    if stats["current_quality_flagged"]:
        return 2, {
            "status": "blocked_by_quality_gate",
            "reason": "current_material_identity_flags",
            "acquisition": manifest.to_dict(),
            "parsing": stats,
        }

    loader = ConabSafraBigQueryLoader(
        project_id=store.project_id,
        dataset_id=os.environ.get("AGROLOG_AGRO_DATASET", "agro"),
        ops_dataset_id=store.dataset_id,
        location=store.bq_location,
        client=store.bq,
    )
    loaded = loader.load(rows, snapshot_id=manifest.sha256, parse_stats=stats)
    return 0, {"acquisition": manifest.to_dict(), "parsing": stats, "load": loaded.to_dict()}
