#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from collector.cloud_store import DriveBigQueryStore
from collector.conab_safra_bigquery import ConabSafraBigQueryLoader
from collector.conab_safra_history import (
    SafraPublication,
    discover_archive_by_pattern,
    discover_publications,
    publication_plausible_for_safra,
)
from collector.conab_safra_pipeline import build_canonical_rows
from collector.models import RunManifest, SourceSpec
from collector.orchestrator import COLLECTOR_VERSION


def select_publications(
    publications: list[SafraPublication],
    *,
    safra: str | None = None,
    min_levantamento: int | None = None,
    max_levantamento: int | None = None,
) -> list[SafraPublication]:
    selected = []
    for item in publications:
        if safra and item.safra != safra:
            continue
        if min_levantamento is not None and (item.levantamento is None or item.levantamento < min_levantamento):
            continue
        if max_levantamento is not None and (item.levantamento is None or item.levantamento > max_levantamento):
            continue
        selected.append(item)
    return selected


def availability_status(item: SafraPublication) -> tuple[bool, str]:
    if not item.data_publicacao:
        return False, "blocked_missing_original_publication_time"
    if not publication_plausible_for_safra(item.safra, item.data_publicacao):
        return False, "blocked_suspected_site_migration_timestamp"
    if not item.availability_basis:
        return False, "blocked_missing_availability_evidence_basis"
    return True, "ready"


def build_plan(publications: list[SafraPublication]) -> list[dict[str, object]]:
    plan = []
    for item in publications:
        verified, status = availability_status(item)
        plan.append({
            "safra": item.safra,
            "levantamento": item.levantamento,
            "data_publicacao": item.data_publicacao,
            "availability_verified": verified,
            "availability_basis": item.availability_basis if verified else None,
            "item_url": item.item_url,
            "attachment_url": item.attachment_url,
            "execution_status": status,
        })
    return plan


def merge_publications(*groups: list[SafraPublication]) -> list[SafraPublication]:
    chosen: dict[tuple[str | None, int | None], SafraPublication] = {}
    for group in groups:
        for item in group:
            key = (item.safra, item.levantamento)
            previous = chosen.get(key)
            if previous is None:
                chosen[key] = item
                continue
            previous_ok, _ = availability_status(previous)
            current_ok, _ = availability_status(item)
            if current_ok and not previous_ok:
                chosen[key] = item
    return sorted(
        chosen.values(),
        key=lambda item: (item.safra or "", item.levantamento or 0),
        reverse=True,
    )


def _download(url: str, timeout: int = 120) -> tuple[bytes, str, str | None, str | None]:
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+verified-historical-backfill)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl(), response.headers.get("Content-Type"), response.headers.get("Last-Modified")


def execute_item(item: SafraPublication, store: DriveBigQueryStore) -> dict[str, object]:
    verified, status = availability_status(item)
    if not verified:
        return {
            "status": status,
            "safra": item.safra,
            "levantamento": item.levantamento,
            "data_publicacao": item.data_publicacao,
            "item_url": item.item_url,
        }

    started = datetime.now(timezone.utc)
    payload, observed_url, content_type, last_modified = _download(item.attachment_url)
    sha256 = hashlib.sha256(payload).hexdigest()
    spec = SourceSpec(
        source_id="conab_safra_graos_xlsx",
        name="CONAB Safra de Graos historical backfill",
        group="dados",
        method="historical_verified_backfill",
        file_extension="xlsx",
        evidence_class="estimado",
        url=item.attachment_url,
    )
    artifact = store.store_raw(spec, payload, sha256, collected_at=started)
    data_coleta = started.isoformat()
    rows, stats = build_canonical_rows(
        payload,
        snapshot_id=sha256,
        data_coleta=data_coleta,
        raw_artifact_ref=artifact.path,
        observed_url=observed_url,
        last_modified=last_modified,
        publication_override=item.data_publicacao,
        availability_verified=True,
        availability_basis=item.availability_basis,
    )
    if not rows or stats.get("current_quality_flagged"):
        return {
            "status": "blocked_by_quality_gate",
            "safra": item.safra,
            "levantamento": item.levantamento,
            "snapshot_id": sha256,
            "parsing": stats,
        }

    loader = ConabSafraBigQueryLoader(
        project_id=store.project_id,
        dataset_id="agro",
        ops_dataset_id=store.dataset_id,
        location=store.bq_location,
        client=store.bq,
    )
    loaded = loader.load(rows, snapshot_id=sha256, parse_stats=stats)
    finished = datetime.now(timezone.utc)
    manifest = RunManifest(
        source_id=spec.source_id,
        group="dados",
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        status=loaded.status,
        collector_version=COLLECTOR_VERSION,
        data_coleta=data_coleta,
        observed_url=observed_url,
        raw_artifact_ref=artifact.path,
        sha256=sha256,
        bytes_read=len(payload),
        content_type=content_type,
        last_modified=last_modified,
        changed=loaded.status == "loaded",
        records_read=stats.get("records_read"),
        records_accepted=stats.get("records_accepted"),
        records_rejected=stats.get("records_rejected"),
        data_publicacao=item.data_publicacao,
        competencia=item.data_publicacao[:7],
        evidence_class="estimado",
        extra={
            "historical_backfill": True,
            "availability_verified": True,
            "availability_basis": item.availability_basis,
            "safra": item.safra,
            "levantamento": item.levantamento,
            "item_url": item.item_url,
            "load": loaded.to_dict(),
        },
    )
    store.write_manifest(manifest)
    return {
        "status": loaded.status,
        "safra": item.safra,
        "levantamento": item.levantamento,
        "snapshot_id": sha256,
        "data_publicacao": item.data_publicacao,
        "data_coleta": data_coleta,
        "availability_verified": True,
        "availability_basis": item.availability_basis,
        "parsing": stats,
        "load": loaded.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill histórico CONAB Safra com disponibilidade original verificada")
    parser.add_argument("--safra")
    parser.add_argument("--min-levantamento", type=int)
    parser.add_argument("--max-levantamento", type=int)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--archive-start-year", type=int)
    parser.add_argument("--archive-end-year", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    listing = discover_publications(max_items=args.max_items)
    archive: list[SafraPublication] = []
    if args.archive_start_year is not None or args.archive_end_year is not None:
        if args.archive_start_year is None or args.archive_end_year is None:
            parser.error("--archive-start-year e --archive-end-year devem ser usados juntos")
        archive = discover_archive_by_pattern(start_year=args.archive_start_year, end_year=args.archive_end_year)
    publications = merge_publications(listing, archive)
    selected = select_publications(
        publications,
        safra=args.safra,
        min_levantamento=args.min_levantamento,
        max_levantamento=args.max_levantamento,
    )
    if args.dry_run:
        plan = build_plan(selected)
        print(json.dumps({
            "mode": "dry_run",
            "items": plan,
            "summary": {
                "total": len(plan),
                "ready": sum(item["execution_status"] == "ready" for item in plan),
                "blocked_missing_publication_time": sum(item["execution_status"] == "blocked_missing_original_publication_time" for item in plan),
                "blocked_suspected_migration": sum(item["execution_status"] == "blocked_suspected_site_migration_timestamp" for item in plan),
                "blocked_missing_evidence_basis": sum(item["execution_status"] == "blocked_missing_availability_evidence_basis" for item in plan),
            },
        }, ensure_ascii=False, indent=2))
        return 0

    store = DriveBigQueryStore()
    results = [execute_item(item, store) for item in reversed(selected)]
    blocked = sum(str(item.get("status", "")).startswith("blocked") for item in results)
    print(json.dumps({"mode": "execute", "results": results, "blocked": blocked}, ensure_ascii=False, indent=2))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
