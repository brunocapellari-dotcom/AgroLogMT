from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .argentina_estimaciones import (
    ArgentinaCropRecord,
    fetch_official_csv,
    parse_estimaciones_csv,
    snapshot_metadata,
)
from .models import RunManifest, SourceSpec
from .orchestrator import COLLECTOR_VERSION, CollectorEngine
from .p0_adapters import AnaHidroAdoptedAdapter
from .storage import sha256_bytes
from .usda_wasde import (
    WasdeArtifact,
    WasdeCell,
    artifact_hash,
    discover_artifacts,
    discover_release_pages,
    fetch_artifact,
    fetch_publication_html,
    flatten_xml,
    publication_date_from_release_url,
)

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime


HYDRO_COLUMNS = {
    "station_code": "VARCHAR NOT NULL",
    "station_name": "VARCHAR",
    "river": "VARCHAR",
    "data_referencia": "DATE NOT NULL",
    "data_publicacao": "TIMESTAMP",
    "data_coleta": "TIMESTAMP NOT NULL",
    "competencia": "VARCHAR NOT NULL",
    "data_hora_medicao": "TIMESTAMP NOT NULL",
    "data_atualizacao": "TIMESTAMP",
    "chuva_mm": "DOUBLE",
    "chuva_status": "VARCHAR",
    "cota_cm": "DOUBLE",
    "cota_status": "VARCHAR",
    "vazao_m3s": "DOUBLE",
    "vazao_status": "VARCHAR",
    "source": "VARCHAR NOT NULL",
    "snapshot_sha256": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
    "evidence_class": "VARCHAR NOT NULL",
    "collector_version": "VARCHAR NOT NULL",
}
HYDRO_ORDER = list(HYDRO_COLUMNS)

ARGENTINA_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "source_id": "VARCHAR NOT NULL",
    "crop": "VARCHAR NOT NULL",
    "crop_id": "VARCHAR NOT NULL",
    "reference_year": "BIGINT",
    "season": "VARCHAR NOT NULL",
    "province": "VARCHAR",
    "province_id": "VARCHAR",
    "department": "VARCHAR",
    "department_id": "VARCHAR",
    "planted_area_ha": "DOUBLE",
    "harvested_area_ha": "DOUBLE",
    "production_t": "DOUBLE",
    "yield_kg_ha": "DOUBLE",
    "evidence_class": "VARCHAR NOT NULL",
    "source_url": "VARCHAR",
    "source_hash": "VARCHAR NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "raw_artifact_ref": "VARCHAR",
    "source_updated_at": "TIMESTAMP",
}
ARGENTINA_ORDER = list(ARGENTINA_COLUMNS)

WASDE_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "semantic_key": "VARCHAR NOT NULL",
    "semantic_occurrence": "BIGINT NOT NULL",
    "cell_index": "BIGINT NOT NULL",
    "source_id": "VARCHAR NOT NULL",
    "release_year": "BIGINT NOT NULL",
    "release_month": "BIGINT NOT NULL",
    "publication_date": "DATE",
    "path": "VARCHAR NOT NULL",
    "attributes_json": "VARCHAR NOT NULL",
    "raw_text": "VARCHAR",
    "numeric_value": "DOUBLE",
    "evidence_class": "VARCHAR NOT NULL",
    "source_url": "VARCHAR NOT NULL",
    "source_hash": "VARCHAR NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "raw_artifact_ref": "VARCHAR",
}
WASDE_ORDER = list(WASDE_COLUMNS)


def _safe_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _stable_hash(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def persist_ana_payload(
    runtime: "ZeroCostRuntime",
    *,
    manifest: RunManifest,
    payload: bytes,
) -> dict[str, Any]:
    body = json.loads(payload.decode("utf-8"))
    if body.get("token_exposed") is not False:
        raise RuntimeError("SECRET_LEAK_GUARD: token exposure flag inválida")
    items = body.get("items") or []
    station_meta = {
        "15400000": ("Porto Velho", "Madeira"),
        "15320002": ("Abunã", "Madeira"),
        "15630000": ("Humaitá", "Madeira"),
        "17730000": ("Itaituba", "Tapajós"),
        "17900000": ("Santarém", "Tapajós/Amazonas"),
    }
    rows: list[dict[str, Any]] = []
    for item in items:
        station = str(item.get("codigoestacao") or "").strip()
        measured = str(item.get("Data_Hora_Medicao") or "").strip()
        if not station or not measured:
            continue
        data_ref = measured[:10]
        name, river = station_meta.get(station, (None, None))
        rows.append({
            "station_code": station,
            "station_name": name,
            "river": river,
            "data_referencia": data_ref,
            "data_publicacao": item.get("Data_Atualizacao"),
            "data_coleta": manifest.data_coleta,
            "competencia": data_ref[:7],
            "data_hora_medicao": measured,
            "data_atualizacao": item.get("Data_Atualizacao"),
            "chuva_mm": _safe_float(item.get("Chuva_Adotada")),
            "chuva_status": str(item.get("Chuva_Adotada_Status")) if item.get("Chuva_Adotada_Status") is not None else None,
            "cota_cm": _safe_float(item.get("Cota_Adotada")),
            "cota_status": str(item.get("Cota_Adotada_Status")) if item.get("Cota_Adotada_Status") is not None else None,
            "vazao_m3s": _safe_float(item.get("Vazao_Adotada")),
            "vazao_status": str(item.get("Vazao_Adotada_Status")) if item.get("Vazao_Adotada_Status") is not None else None,
            "source": "ANA_HIDROWEB_NEW_API",
            "snapshot_sha256": manifest.sha256,
            "raw_artifact_ref": manifest.raw_artifact_ref,
            "evidence_class": "observado",
            "collector_version": manifest.collector_version,
        })
    if not rows:
        raise RuntimeError("ANA retornou zero registros utilizáveis")

    runtime.analytics.ensure_table("hidrologia", "hydro_station_telemetry", HYDRO_COLUMNS)
    inserted = 0
    for row in rows:
        exists = runtime.analytics.scalar(
            """
            SELECT COUNT(*) FROM hidrologia.hydro_station_telemetry
            WHERE station_code=? AND data_hora_medicao=?
              AND COALESCE(CAST(data_atualizacao AS VARCHAR),'')=COALESCE(CAST(? AS VARCHAR),'')
            """,
            [row["station_code"], row["data_hora_medicao"], row["data_atualizacao"]],
        )
        if exists:
            continue
        inserted += runtime.analytics.insert_rows(
            "hidrologia", "hydro_station_telemetry", [row], columns=HYDRO_ORDER
        )
    parquet = runtime.analytics.export_table_parquet("hidrologia", "hydro_station_telemetry")
    return {
        "table": "hidrologia.hydro_station_telemetry",
        "records_read": len(rows),
        "inserted": inserted,
        "duplicates_skipped": len(rows) - inserted,
        "parquet": str(parquet),
    }


def run_ana_source(runtime: "ZeroCostRuntime", spec: SourceSpec) -> tuple[int, dict[str, Any]]:
    def resolver(method: str):
        if method == "ana_hidroweb_adopted":
            return AnaHidroAdoptedAdapter()
        from .adapters import get_adapter
        return get_adapter(method)

    outcome = CollectorEngine(store=runtime.raw, adapter_resolver=resolver).run_source_capture(spec)
    manifest = outcome.manifest
    if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
        return 1, {"status": "source_error", "acquisition": manifest.to_dict()}
    try:
        load = persist_ana_payload(runtime, manifest=manifest, payload=outcome.payload)
        return 0, {"status": "ok", "acquisition": manifest.to_dict(), "load": load}
    except Exception as exc:
        return 2, {
            "status": "blocked_by_quality_gate",
            "acquisition": manifest.to_dict(),
            "error": f"{type(exc).__name__}: {exc}",
        }


def persist_argentina_records(
    runtime: "ZeroCostRuntime",
    records: list[ArgentinaCropRecord],
    *,
    snapshot_id: str,
    source_hash: str,
    data_coleta: str,
    source_url: str,
    raw_artifact_ref: str | None,
    source_updated_at: str | None,
) -> dict[str, Any]:
    if not records:
        raise ValueError("Argentina local loader recusou lote vazio")
    runtime.analytics.ensure_table("agro", "argentina_estimaciones", ARGENTINA_COLUMNS)
    payload: dict[str, dict[str, Any]] = {}
    for row in records:
        natural = [
            row.crop_id,
            str(row.year or ""),
            row.season,
            row.province_id or row.province,
            row.department_id or row.department,
        ]
        record_id = _stable_hash(natural)
        payload[record_id] = {
            "snapshot_id": snapshot_id,
            "record_id": record_id,
            "source_id": row.source_id,
            "crop": row.crop,
            "crop_id": row.crop_id,
            "reference_year": row.year,
            "season": row.season,
            "province": row.province or None,
            "province_id": row.province_id,
            "department": row.department or None,
            "department_id": row.department_id,
            "planted_area_ha": row.planted_area_ha,
            "harvested_area_ha": row.harvested_area_ha,
            "production_t": row.production_t,
            "yield_kg_ha": row.yield_kg_ha,
            "evidence_class": row.evidence_class,
            "source_url": source_url,
            "source_hash": source_hash,
            "data_coleta": data_coleta,
            "raw_artifact_ref": raw_artifact_ref,
            "source_updated_at": source_updated_at,
        }
    rows = list(payload.values())
    existing = int(runtime.analytics.scalar(
        "SELECT COUNT(*) FROM agro.argentina_estimaciones WHERE snapshot_id=?",
        [snapshot_id],
    ) or 0)
    if existing and existing != len(rows):
        raise RuntimeError(f"Argentina tie-out local falhou: esperado={len(rows)} persistido={existing}")
    inserted = 0 if existing else runtime.analytics.insert_rows(
        "agro", "argentina_estimaciones", rows, columns=ARGENTINA_ORDER
    )
    parquet = runtime.analytics.export_table_parquet("agro", "argentina_estimaciones")
    return {
        "table": "agro.argentina_estimaciones",
        "snapshot_id": snapshot_id,
        "records": len(rows),
        "inserted": inserted,
        "parquet": str(parquet),
    }


def run_argentina_source(runtime: "ZeroCostRuntime", *, timeout: int = 60) -> tuple[int, dict[str, Any]]:
    started = datetime.now(timezone.utc)
    source_id = "sagyp_argentina"
    manifest = RunManifest(
        source_id=source_id,
        group="dados",
        started_at=started.isoformat(),
        finished_at=started.isoformat(),
        status="running",
        collector_version=COLLECTOR_VERSION,
        data_coleta=started.isoformat(),
        evidence_class="estimado",
    )
    try:
        payload, url, source_updated_at = fetch_official_csv(timeout=timeout)
        meta = snapshot_metadata(payload, collected_at=datetime.now(timezone.utc))
        spec = SourceSpec(
            source_id=source_id,
            name="Argentina Estimaciones Agrícolas",
            group="dados",
            method="official_csv",
            file_extension="csv",
            evidence_class="estimado",
        )
        raw = runtime.raw.store_raw(spec, payload, meta["source_hash"])
        records = parse_estimaciones_csv(payload)
        load = persist_argentina_records(
            runtime,
            records,
            snapshot_id=meta["snapshot_id"],
            source_hash=meta["source_hash"],
            data_coleta=meta["data_coleta"],
            source_url=url,
            raw_artifact_ref=raw.path,
            source_updated_at=source_updated_at,
        )
        manifest.finished_at = datetime.now(timezone.utc).isoformat()
        manifest.status = "updated"
        manifest.data_coleta = meta["data_coleta"]
        manifest.observed_url = url
        manifest.raw_artifact_ref = raw.path
        manifest.sha256 = meta["source_hash"]
        manifest.bytes_read = len(payload)
        manifest.records_read = len(records)
        manifest.records_accepted = len(records)
        manifest.records_rejected = 0
        manifest.data_publicacao = source_updated_at[:10] if source_updated_at else None
        manifest.extra = {"load": load, "backend": "duckdb"}
        runtime.raw.write_manifest(manifest)
        runtime.raw.save_state(source_id, {
            "last_sha256": meta["source_hash"],
            "last_checked_at": manifest.finished_at,
            "last_raw_artifact_ref": raw.path,
            "analytical_backend": "duckdb",
        })
        return 0, {"status": "ok", "acquisition": manifest.to_dict(), "load": load}
    except Exception as exc:
        manifest.finished_at = datetime.now(timezone.utc).isoformat()
        manifest.status = "error"
        manifest.error = f"{type(exc).__name__}: {exc}"
        try:
            runtime.raw.write_manifest(manifest)
        except Exception:
            pass
        return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict()}


def _latest_wasde_xml(*, timeout: int = 60) -> tuple[WasdeArtifact, str | None]:
    listing = fetch_publication_html(timeout=timeout)
    pages = sorted(discover_release_pages(listing), reverse=True)
    for page in pages[:12]:
        html = fetch_publication_html(url=page, timeout=timeout)
        artifacts = [item for item in discover_artifacts(html, base_url=page) if item.format == "xml"]
        if artifacts:
            return max(artifacts, key=lambda item: (item.year, item.month, item.version or "")), publication_date_from_release_url(page)
    direct = [item for item in discover_artifacts(listing) if item.format == "xml"]
    if direct:
        return max(direct, key=lambda item: (item.year, item.month, item.version or "")), None
    raise RuntimeError("USDA WASDE: nenhum XML oficial descoberto")


def persist_wasde_cells(
    runtime: "ZeroCostRuntime",
    cells: list[WasdeCell],
    *,
    artifact: WasdeArtifact,
    payload: bytes,
    data_coleta: str,
    publication_date: str | None,
    raw_artifact_ref: str | None,
) -> dict[str, Any]:
    if not cells:
        raise ValueError("WASDE local loader recusou lote vazio")
    runtime.analytics.ensure_table("global_market", "usda_wasde_cells", WASDE_COLUMNS)
    digest = artifact_hash(payload)
    snapshot_id = f"wasde:{artifact.year:04d}-{artifact.month:02d}:{digest[:24]}"
    occurrences: Counter[tuple[str, str]] = Counter()
    rows: list[dict[str, Any]] = []
    for cell in cells:
        key = (cell.path, cell.attributes_json)
        occurrence = occurrences[key]
        occurrences[key] += 1
        semantic_key = _stable_hash([cell.path, cell.attributes_json, str(occurrence)])
        rows.append({
            "snapshot_id": snapshot_id,
            "record_id": _stable_hash([snapshot_id, str(cell.cell_index), semantic_key]),
            "semantic_key": semantic_key,
            "semantic_occurrence": occurrence,
            "cell_index": cell.cell_index,
            "source_id": "usda_wasde",
            "release_year": artifact.year,
            "release_month": artifact.month,
            "publication_date": publication_date,
            "path": cell.path,
            "attributes_json": cell.attributes_json,
            "raw_text": cell.raw_text or None,
            "numeric_value": cell.numeric_value,
            "evidence_class": "INFORMADO",
            "source_url": artifact.url,
            "source_hash": digest,
            "data_coleta": data_coleta,
            "raw_artifact_ref": raw_artifact_ref,
        })
    existing = int(runtime.analytics.scalar(
        "SELECT COUNT(*) FROM global_market.usda_wasde_cells WHERE snapshot_id=?",
        [snapshot_id],
    ) or 0)
    if existing and existing != len(rows):
        raise RuntimeError(f"WASDE tie-out local falhou: esperado={len(rows)} persistido={existing}")
    inserted = 0 if existing else runtime.analytics.insert_rows(
        "global_market", "usda_wasde_cells", rows, columns=WASDE_ORDER
    )
    parquet = runtime.analytics.export_table_parquet("global_market", "usda_wasde_cells")
    return {
        "table": "global_market.usda_wasde_cells",
        "snapshot_id": snapshot_id,
        "records": len(rows),
        "inserted": inserted,
        "parquet": str(parquet),
    }


def run_wasde_source(runtime: "ZeroCostRuntime", *, timeout: int = 60) -> tuple[int, dict[str, Any]]:
    started = datetime.now(timezone.utc)
    manifest = RunManifest(
        source_id="usda_wasde",
        group="dados",
        started_at=started.isoformat(),
        finished_at=started.isoformat(),
        status="running",
        collector_version=COLLECTOR_VERSION,
        data_coleta=started.isoformat(),
        evidence_class="estimado",
    )
    try:
        artifact, publication_date = _latest_wasde_xml(timeout=timeout)
        payload = fetch_artifact(artifact, timeout=timeout)
        digest = sha256_bytes(payload)
        collected = datetime.now(timezone.utc)
        spec = SourceSpec(
            source_id="usda_wasde",
            name="USDA WASDE",
            group="dados",
            method="official_xml",
            file_extension="xml",
            evidence_class="estimado",
        )
        raw = runtime.raw.store_raw(spec, payload, digest, collected_at=collected)
        cells = flatten_xml(payload)
        load = persist_wasde_cells(
            runtime,
            cells,
            artifact=artifact,
            payload=payload,
            data_coleta=collected.isoformat(),
            publication_date=publication_date,
            raw_artifact_ref=raw.path,
        )
        manifest.finished_at = datetime.now(timezone.utc).isoformat()
        manifest.status = "updated"
        manifest.data_coleta = collected.isoformat()
        manifest.observed_url = artifact.url
        manifest.raw_artifact_ref = raw.path
        manifest.sha256 = digest
        manifest.bytes_read = len(payload)
        manifest.records_read = len(cells)
        manifest.records_accepted = len(cells)
        manifest.records_rejected = 0
        manifest.data_referencia = publication_date or f"{artifact.year:04d}-{artifact.month:02d}-01"
        manifest.data_publicacao = publication_date
        manifest.competencia = f"{artifact.year:04d}-{artifact.month:02d}"
        manifest.extra = {"load": load, "backend": "duckdb", "format": artifact.format}
        runtime.raw.write_manifest(manifest)
        runtime.raw.save_state("usda_wasde", {
            "last_sha256": digest,
            "competencia": manifest.competencia,
            "last_checked_at": manifest.finished_at,
            "last_raw_artifact_ref": raw.path,
            "analytical_backend": "duckdb",
        })
        return 0, {"status": "ok", "acquisition": manifest.to_dict(), "load": load}
    except Exception as exc:
        manifest.finished_at = datetime.now(timezone.utc).isoformat()
        manifest.status = "error"
        manifest.error = f"{type(exc).__name__}: {exc}"
        try:
            runtime.raw.write_manifest(manifest)
        except Exception:
            pass
        return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict()}
