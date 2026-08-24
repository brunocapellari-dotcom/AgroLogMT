from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .cloud_store import DriveBigQueryStore
from .models import RunManifest, SourceSpec
from .nasa_power import DEFAULT_PARAMETERS, build_url, parse_response
from .nasa_power_bigquery import NasaPowerBigQueryLoader, power_rows
from .orchestrator import COLLECTOR_VERSION

SOURCE_ID = "nasa_power_mt_pilot_lucas"


def _window(spec: SourceSpec) -> tuple[datetime, datetime]:
    tz = ZoneInfo(spec.source_timezone)
    now = datetime.now(tz)
    lag_days = int(spec.options.get("lag_days", 2))
    days_back = int(spec.options.get("days_back", 7))
    if lag_days < 0 or days_back < 1 or days_back > 366:
        raise ValueError("janela NASA POWER inválida")
    end = now - timedelta(days=lag_days)
    start = end - timedelta(days=days_back - 1)
    return start, end


def run_nasa_power_pipeline(spec: SourceSpec, store: DriveBigQueryStore) -> tuple[int, dict[str, Any]]:
    import requests

    started = datetime.now(timezone.utc)
    start, end = _window(spec)
    latitude = float(spec.options["latitude"])
    longitude = float(spec.options["longitude"])
    parameters = tuple(spec.options.get("parameters", DEFAULT_PARAMETERS))
    url = build_url(latitude=latitude, longitude=longitude, start=start.date(), end=end.date(), parameters=parameters)
    try:
        response = requests.get(
            url, headers={"User-Agent": "AgroLogMT/0.1 (+NASA POWER pipeline)"},
            timeout=(20, int(spec.options.get("timeout_seconds", 90))), allow_redirects=True,
        )
        response.raise_for_status()
        if not response.url.lower().startswith("https://"):
            raise RuntimeError("NASA POWER redirecionou para transporte não HTTPS")
        payload = response.content
        source_hash = hashlib.sha256(payload).hexdigest()
        collected = datetime.now(timezone.utc)
        raw = store.store_raw(spec, payload, source_hash, collected_at=collected)
        body = json.loads(payload.decode("utf-8"))
        parsed = parse_response(body)
        expected = set(parameters)
        present = {row.parameter for row in parsed}
        missing = sorted(expected - present)
        if missing:
            raise RuntimeError(f"NASA POWER sem parâmetros esperados: {missing}")
        manifest = RunManifest(
            source_id=spec.source_id, group=spec.group,
            started_at=started.isoformat(), finished_at=datetime.now(timezone.utc).isoformat(),
            status="ok", collector_version=COLLECTOR_VERSION, data_coleta=collected.isoformat(),
            observed_url=response.url, raw_artifact_ref=raw.path, sha256=source_hash,
            bytes_read=len(payload), content_type=response.headers.get("Content-Type"),
            last_modified=response.headers.get("Last-Modified"), changed=True,
            records_read=len(parsed), records_accepted=len(parsed), records_rejected=0,
            data_referencia=end.date().isoformat(), evidence_class="estimado",
            extra={"latitude": latitude, "longitude": longitude, "start": start.date().isoformat(), "end": end.date().isoformat(), "evidence_subtype": "nasa_power_gridded"},
        )
        store.write_manifest(manifest)
        rows = power_rows(
            parsed, snapshot_id=source_hash, data_coleta=collected.isoformat(), source_url=response.url,
            source_hash=source_hash, raw_artifact_ref=raw.path,
        )
        loader = NasaPowerBigQueryLoader(
            project_id=store.project_id, dataset_id=os.environ.get("AGROLOG_CLIMATE_DATASET", "clima"),
            location=store.bq_location, client=store.bq,
        )
        loaded = loader.load(rows, snapshot_id=source_hash)
        store.save_state(spec.source_id, {"last_sha256": source_hash, "canonical_loaded_snapshot": source_hash, "checked_at": manifest.finished_at})
        return 0, {"acquisition": manifest.to_dict(), "load": loaded}
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        manifest = RunManifest(
            source_id=spec.source_id, group=spec.group, started_at=started.isoformat(), finished_at=finished.isoformat(),
            status="error", collector_version=COLLECTOR_VERSION, data_coleta=finished.isoformat(),
            observed_url=url, evidence_class="estimado", error=f"{type(exc).__name__}: {exc}",
        )
        try:
            store.write_manifest(manifest)
        except Exception:
            pass
        return 1, {"acquisition": manifest.to_dict()}
