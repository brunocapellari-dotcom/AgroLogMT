#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from collector.cloud_store import DriveBigQueryStore
from collector.comexstat import URL_TEMPLATES, dataset_url, stream_download
from collector.comexstat_bigquery import ComexStatBigQueryLoader, write_ndjson
from collector.models import RunManifest, SourceSpec
from collector.orchestrator import COLLECTOR_VERSION

VARIANTS = tuple(URL_TEMPLATES)


def build_plan(start_year: int, end_year: int, variants: tuple[str, ...]) -> list[dict[str, object]]:
    if start_year > end_year:
        raise ValueError("start_year posterior a end_year")
    return [
        {"year": year, "variant": variant, "url": dataset_url(variant, year), "target_dataset": "comercio_exterior"}
        for year in range(start_year, end_year + 1)
        for variant in variants
    ]


def _http_timestamp(last_modified: str | None) -> str | None:
    if not last_modified:
        return None
    try:
        parsed = parsedate_to_datetime(last_modified)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def execute_item(item: dict[str, object], store: DriveBigQueryStore) -> dict[str, object]:
    year = int(item["year"])
    variant = str(item["variant"])
    url = str(item["url"])
    started = datetime.now(timezone.utc)
    spec = SourceSpec(
        source_id="mdic_comexstat_open_data",
        name=f"Comex Stat {variant} {year}",
        group="dados",
        method="streaming_https",
        file_extension="csv",
        evidence_class="observado",
        url=url,
    )

    with tempfile.TemporaryDirectory(prefix="agrolog_comex_") as tmp:
        csv_path = Path(tmp) / f"{variant}_{year}.csv"
        ndjson_path = Path(tmp) / f"{variant}_{year}.ndjson"
        download = stream_download(url, csv_path)
        artifact = store.store_raw_file(spec, csv_path, download.sha256, collected_at=started)
        data_coleta = started.isoformat()
        data_publicacao = _http_timestamp(download.last_modified)
        normalized = write_ndjson(
            csv_path,
            ndjson_path,
            variant,
            snapshot_id=download.sha256,
            data_coleta=data_coleta,
            data_publicacao=data_publicacao,
            source_url=download.url,
            source_hash=download.sha256,
            raw_artifact_ref=artifact.path,
        )
        loader = ComexStatBigQueryLoader(
            project_id=store.project_id,
            dataset_id="comercio_exterior",
            location=store.bq_location,
            client=store.bq,
        )
        loaded = loader.load_ndjson(variant, ndjson_path, snapshot_id=download.sha256)

    finished = datetime.now(timezone.utc)
    manifest = RunManifest(
        source_id=spec.source_id,
        group="dados",
        started_at=started.isoformat(),
        finished_at=finished.isoformat(),
        status=str(loaded["status"]),
        collector_version=COLLECTOR_VERSION,
        data_coleta=started.isoformat(),
        observed_url=download.url,
        raw_artifact_ref=artifact.path,
        sha256=download.sha256,
        bytes_read=download.size,
        content_type=download.content_type,
        last_modified=download.last_modified,
        changed=loaded["status"] == "loaded",
        records_read=int(normalized["rows"]),
        records_accepted=int(normalized["unique_record_ids"]),
        duplicates_removed=int(normalized["exact_duplicate_rows"]),
        data_publicacao=data_publicacao,
        competencia=f"{year}",
        evidence_class="observado",
        extra={
            "historical_backfill": True,
            "variant": variant,
            "year": year,
            "target_dataset": "comercio_exterior",
            "availability_verified": False,
            "availability_note": "HTTP Last-Modified e preservado como metadado, mas nao prova a data original de disponibilidade de cada competencia mensal.",
            "normalization": normalized,
            "load": loaded,
        },
    )
    store.write_manifest(manifest)
    return {
        "year": year,
        "variant": variant,
        "snapshot_id": download.sha256,
        "raw_artifact_ref": artifact.path,
        "normalization": normalized,
        "load": loaded,
        "availability_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Comex Stat anual em streaming, sem desabilitar TLS")
    parser.add_argument("--start-year", type=int, default=1997)
    parser.add_argument("--end-year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--variant", action="append", choices=VARIANTS, dest="variants")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    variants = tuple(args.variants or VARIANTS)
    plan = build_plan(args.start_year, args.end_year, variants)
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "items": plan}, ensure_ascii=False, indent=2))
        return 0

    store = DriveBigQueryStore()
    results = [execute_item(item, store) for item in plan]
    print(json.dumps({"mode": "execute", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
