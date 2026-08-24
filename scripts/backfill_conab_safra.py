#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from collector.cloud_store import DriveBigQueryStore
from collector.conab_safra_bigquery import ConabSafraBigQueryLoader
from collector.conab_safra_history import SafraPublication, discover_publications
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


def build_plan(publications: list[SafraPublication]) -> list[dict[str, object]]:
    return [
        {
            "safra": item.safra,
            "levantamento": item.levantamento,
            "data_publicacao": item.data_publicacao,
            "availability_verified": bool(item.data_publicacao),
            "item_url": item.item_url,
            "attachment_url": item.attachment_url,
            "execution_status": "ready" if item.data_publicacao else "blocked_missing_original_publication_time",
        }
        for item in publications
    ]


def _download(url: str, timeout: int = 120) -> tuple[bytes, str, str | None, str | None]:
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+verified-historical-backfill)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.geturl(), response.headers.get("Content-Type"), response.headers.get("Last-Modified")


def execute_item(item: SafraPublication, store: DriveBigQueryStore) -> dict[str, object]:
    if not item.data_publicacao:
        return {
            "status": "blocked_missing_original_publication_time",
            "safra": item.safra,
            "levantamento": item.levantamento,
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
        availability_basis="official_page_timestamp",
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
            "availability_basis": "official_page_timestamp",
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
        "parsing": stats,
        "load": loaded.to_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill histórico CONAB Safra com disponibilidade original verificada")
    parser.add_argument("--safra")
    parser.add_argument("--min-levantamento", type=int)
    parser.add_argument("--max-levantamento", type=int)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    publications = discover_publications(max_items=args.max_items)
    selected = select_publications(
        publications,
        safra=args.safra,
        min_levantamento=args.min_levantamento,
        max_levantamento=args.max_levantamento,
    )
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "items": build_plan(selected)}, ensure_ascii=False, indent=2))
        return 0

    store = DriveBigQueryStore()
    results = [execute_item(item, store) for item in reversed(selected)]
    blocked = sum(str(item.get("status", "")).startswith("blocked") for item in results)
    print(json.dumps({"mode": "execute", "results": results, "blocked": blocked}, ensure_ascii=False, indent=2))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
