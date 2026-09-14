from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from collector.cloud_store import DriveBigQueryStore
from collector.lineup_normalizer import normalize_lineup_row
from collector.models import RunManifest, SourceSpec
from collector.official_lineup_html import FetchedHtml, fetch_official_html, parse_official_lineup_html
from collector.shipping_bigquery import ShippingBigQueryStore


DEFAULT_CONFIG = Path(__file__).with_name("config") / "maritime_lineup_sources.v1.json"
COLLECTOR_VERSION = "maritime-lineup-html-v1"
SOURCE_TIMEZONE = "America/Sao_Paulo"


def load_source_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("version") != "1.0":
        raise ValueError("versão de maritime_lineup_sources não suportada")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifesto maritime line-up sem sources")
    seen: set[str] = set()
    for source in sources:
        required = {"source_id", "port_id", "url", "parser_mode", "enabled", "evidence_class"}
        missing = sorted(required - set(source))
        if missing:
            raise ValueError(f"fonte line-up incompleta {source.get('source_id')}: {missing}")
        source_id = str(source["source_id"])
        if source_id in seen:
            raise ValueError(f"source_id duplicado: {source_id}")
        seen.add(source_id)
        if source["evidence_class"] != "INFORMADO":
            raise ValueError(f"line-up oficial deve ser INFORMADO: {source_id}")
    return payload


def _raw_spec(source: dict[str, Any]) -> SourceSpec:
    return SourceSpec(
        source_id=str(source["source_id"]),
        name=f"Maritime line-up {source['port_id']}",
        group="dados",
        method="http_html",
        enabled=True,
        url=str(source["url"]),
        expected_frequency="intraday",
        file_extension="html",
        evidence_class="observado",
        source_timezone=SOURCE_TIMEZONE,
        notes="Programação portuária oficial; não comprova realização física.",
    )


def _lineup_bq_row(call, *, snapshot_id: str, source_hash: str, raw_artifact_ref: str) -> dict[str, Any]:
    return {
        "call_id": call.call_id,
        "snapshot_id": snapshot_id,
        "port_id": call.port_id,
        "terminal_id": call.terminal_id,
        "vessel_name": call.vessel_name,
        "imo": call.imo,
        "mmsi": call.mmsi,
        "eta": call.eta_utc.isoformat(),
        "product": call.product,
        "planned_volume_t": call.planned_volume_t,
        "lineup_status": call.lineup_status,
        "source_id": call.source_id,
        "collected_at": call.collected_at.isoformat() if hasattr(call.collected_at, "isoformat") else str(call.collected_at),
        "source_hash": source_hash,
        "raw_artifact_ref": raw_artifact_ref,
    }


def ingest_html_source(
    source: dict[str, Any],
    *,
    raw_store: DriveBigQueryStore,
    shipping_store: ShippingBigQueryStore,
    fetcher: Callable[..., FetchedHtml] = fetch_official_html,
    now: datetime | None = None,
) -> dict[str, Any]:
    collected_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    started_at = collected_at.isoformat()
    spec = _raw_spec(source)
    fetched = fetcher(str(source["url"]))
    source_hash = hashlib.sha256(fetched.body).hexdigest()
    artifact = raw_store.store_raw(spec, fetched.body, source_hash, collected_at=collected_at)
    snapshot_id = f"{source['source_id']}:{collected_at.strftime('%Y%m%dT%H%M%SZ')}:{source_hash[:16]}"

    previous = raw_store.load_state(str(source["source_id"]))
    changed = previous.get("sha256") != source_hash
    parsed_rows = parse_official_lineup_html(fetched.text, str(source["parser_mode"]))

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for index, row in enumerate(parsed_rows):
        try:
            call = normalize_lineup_row(
                row,
                port_id=str(source["port_id"]),
                snapshot_id=snapshot_id,
                collected_at=collected_at,
                source_id=str(source["source_id"]),
                source_timezone=SOURCE_TIMEZONE,
            )
            # HTML programming adapters are not allowed to promote physical realization.
            if call.lineup_status != "PROGRAMMED":
                raise ValueError(f"HTML programming source promoted invalid status {call.lineup_status}")
            accepted.append(
                _lineup_bq_row(
                    call,
                    snapshot_id=snapshot_id,
                    source_hash=source_hash,
                    raw_artifact_ref=artifact.path,
                )
            )
        except Exception as exc:  # keep source-level run auditable; never fabricate a row
            rejected.append({"row": str(index), "error_type": type(exc).__name__, "error": str(exc)[:500]})

    if not accepted:
        manifest = RunManifest(
            source_id=str(source["source_id"]),
            group="dados",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            status="ERROR",
            collector_version=COLLECTOR_VERSION,
            data_coleta=collected_at.isoformat(),
            observed_url=fetched.url,
            raw_artifact_ref=artifact.path,
            sha256=source_hash,
            bytes_read=len(fetched.body),
            content_type=fetched.content_type,
            etag=fetched.etag,
            last_modified=fetched.last_modified,
            changed=changed,
            records_read=len(parsed_rows),
            records_accepted=0,
            records_rejected=len(rejected),
            evidence_class="observado",
            error="nenhuma linha de line-up aceita; fonte/parser bloqueado",
            extra={"port_id": source["port_id"], "parser_mode": source["parser_mode"], "rejections": rejected[:20]},
        )
        raw_store.write_manifest(manifest)
        raise RuntimeError(f"{source['source_id']}: nenhuma linha aceita")

    inserted = shipping_store.load_lineup(accepted)
    raw_store.save_state(
        str(source["source_id"]),
        {
            "sha256": source_hash,
            "snapshot_id": snapshot_id,
            "collected_at": collected_at.isoformat(),
            "raw_artifact_ref": artifact.path,
            "records_accepted": len(accepted),
        },
    )
    status = "OK" if not rejected else "PARTIAL"
    manifest = RunManifest(
        source_id=str(source["source_id"]),
        group="dados",
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        collector_version=COLLECTOR_VERSION,
        data_coleta=collected_at.isoformat(),
        observed_url=fetched.url,
        raw_artifact_ref=artifact.path,
        sha256=source_hash,
        bytes_read=len(fetched.body),
        content_type=fetched.content_type,
        etag=fetched.etag,
        last_modified=fetched.last_modified,
        changed=changed,
        records_read=len(parsed_rows),
        records_accepted=len(accepted),
        records_rejected=len(rejected),
        duplicates_removed=0,
        evidence_class="observado",
        extra={
            "port_id": source["port_id"],
            "parser_mode": source["parser_mode"],
            "lineup_evidence_class": "INFORMADO",
            "inserted": inserted,
            "rejections": rejected[:20],
        },
    )
    raw_store.write_manifest(manifest)
    return {
        "source_id": source["source_id"],
        "port_id": source["port_id"],
        "status": status,
        "snapshot_id": snapshot_id,
        "sha256": source_hash,
        "raw_artifact_ref": artifact.path,
        "records_read": len(parsed_rows),
        "records_accepted": len(accepted),
        "records_rejected": len(rejected),
        "inserted": inserted,
        "changed": changed,
    }


def run_enabled_sources(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    selected_source_id: str | None = None,
) -> dict[str, Any]:
    config = load_source_config(config_path)
    raw_store = DriveBigQueryStore()
    shipping_store = ShippingBigQueryStore()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    selected = [
        source for source in config["sources"]
        if source.get("enabled") and (not selected_source_id or source["source_id"] == selected_source_id)
    ]
    if selected_source_id and not selected:
        raise ValueError(f"source_id não habilitado ou inexistente: {selected_source_id}")
    for source in selected:
        try:
            results.append(ingest_html_source(source, raw_store=raw_store, shipping_store=shipping_store))
        except Exception as exc:
            errors.append({"source_id": str(source["source_id"]), "error_type": type(exc).__name__, "error": str(exc)[:1000]})
    return {
        "collector_version": COLLECTOR_VERSION,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "sources_attempted": len(selected),
        "sources_ok": len(results),
        "sources_failed": len(errors),
        "results": results,
        "errors": errors,
    }


def main() -> int:
    report = run_enabled_sources(
        config_path=os.environ.get("MARITIME_LINEUP_CONFIG", str(DEFAULT_CONFIG)),
        selected_source_id=os.environ.get("MARITIME_LINEUP_SOURCE_ID") or None,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if report["sources_failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
