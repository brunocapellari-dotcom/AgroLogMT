from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .imea_operational_xlsx import parse_workbook
from .models import RunManifest, SourceSpec
from .orchestrator import COLLECTOR_VERSION

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime

INDICATOR_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "source_sheet": "VARCHAR NOT NULL",
    "data_referencia": "DATE NOT NULL",
    "produto": "VARCHAR NOT NULL",
    "metric_name": "VARCHAR NOT NULL",
    "valor": "DOUBLE NOT NULL",
    "unidade_origem": "VARCHAR",
    "unidade_canonica": "VARCHAR",
    "local": "VARCHAR",
    "evidence_class": "VARCHAR NOT NULL",
    "evidence_subtype": "VARCHAR NOT NULL",
    "negotiated": "BOOLEAN NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "source_hash": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
}
INDICATOR_ORDER = list(INDICATOR_COLUMNS)

FREIGHT_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "data_referencia": "DATE NOT NULL",
    "produto": "VARCHAR NOT NULL",
    "metric_name": "VARCHAR NOT NULL",
    "origem": "VARCHAR NOT NULL",
    "destino": "VARCHAR NOT NULL",
    "valor": "DOUBLE NOT NULL",
    "unidade_origem": "VARCHAR",
    "unidade_canonica": "VARCHAR",
    "evidence_class": "VARCHAR NOT NULL",
    "evidence_subtype": "VARCHAR NOT NULL",
    "negotiated": "BOOLEAN NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "source_hash": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
}
FREIGHT_ORDER = list(FREIGHT_COLUMNS)

PROGRESS_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "source_sheet": "VARCHAR NOT NULL",
    "data_referencia": "DATE NOT NULL",
    "produto": "VARCHAR NOT NULL",
    "safra": "VARCHAR NOT NULL",
    "regiao": "VARCHAR NOT NULL",
    "metric_name": "VARCHAR NOT NULL",
    "valor": "DOUBLE NOT NULL",
    "unidade_canonica": "VARCHAR NOT NULL",
    "evidence_class": "VARCHAR NOT NULL",
    "evidence_subtype": "VARCHAR NOT NULL",
    "data_coleta": "TIMESTAMP NOT NULL",
    "source_hash": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
}
PROGRESS_ORDER = list(PROGRESS_COLUMNS)


def _load_group(
    runtime: "ZeroCostRuntime",
    *,
    schema: str,
    table: str,
    columns: dict[str, str],
    order: list[str],
    rows: list[dict[str, Any]],
    snapshot_id: str,
) -> dict[str, Any]:
    if not rows:
        return {
            "table": f"{schema}.{table}",
            "status": "empty",
            "records_input": 0,
            "records_unique": 0,
            "inserted": 0,
        }
    unique = {str(row["record_id"]): row for row in rows}
    canonical = list(unique.values())
    runtime.analytics.ensure_table(schema, table, columns)
    existing = int(runtime.analytics.scalar(
        f"SELECT COUNT(*) FROM {schema}.{table} WHERE snapshot_id=?",  # nosec B608 - schema/table are code-owned constants
        [snapshot_id],
    ) or 0)
    if existing and existing != len(canonical):
        raise RuntimeError(
            f"Tie-out IMEA local falhou: table={schema}.{table} "
            f"snapshot={snapshot_id} esperado={len(canonical)} persistido={existing}"
        )
    inserted = 0 if existing else runtime.analytics.insert_rows(
        schema, table, canonical, columns=order
    )
    parquet = runtime.analytics.export_table_parquet(schema, table)
    return {
        "table": f"{schema}.{table}",
        "status": "already_loaded" if existing else "loaded",
        "records_input": len(rows),
        "records_unique": len(canonical),
        "records_existing": existing,
        "inserted": inserted,
        "parquet": str(parquet),
    }


def persist_imea_parsed(
    runtime: "ZeroCostRuntime",
    parsed: dict[str, Any],
    *,
    snapshot_id: str,
    data_coleta: str,
    source_hash: str,
    raw_artifact_ref: str | None,
) -> dict[str, Any]:
    records = parsed.get("records") or []
    if not records:
        raise ValueError("IMEA local loader recusou lote vazio")
    qa = dict(parsed.get("qa") or {})
    if qa.get("natural_key_duplicates"):
        raise RuntimeError("IMEA workbook com duplicidade de chave natural")
    if qa.get("progress_out_of_range"):
        raise RuntimeError("IMEA workbook com progresso fora de [0,1]")

    indicators: list[dict[str, Any]] = []
    freight: list[dict[str, Any]] = []
    progress: list[dict[str, Any]] = []
    common = {
        "snapshot_id": snapshot_id,
        "data_coleta": data_coleta,
        "source_hash": source_hash,
        "raw_artifact_ref": raw_artifact_ref,
    }
    for source in records:
        sheet = str(source.get("source_sheet") or "")
        if sheet in {"indicadores diarios", "indicadores semanais"}:
            indicators.append({
                key: source.get(key)
                for key in (
                    "record_id", "source_sheet", "data_referencia", "produto", "metric_name",
                    "valor", "unidade_origem", "unidade_canonica", "local",
                    "evidence_class", "evidence_subtype", "negotiated",
                )
            } | common)
        elif sheet == "frete":
            freight.append({
                key: source.get(key)
                for key in (
                    "record_id", "data_referencia", "produto", "metric_name", "origem", "destino",
                    "valor", "unidade_origem", "unidade_canonica",
                    "evidence_class", "evidence_subtype", "negotiated",
                )
            } | common)
        else:
            progress.append({
                key: source.get(key)
                for key in (
                    "record_id", "source_sheet", "data_referencia", "produto", "safra", "regiao",
                    "metric_name", "valor", "unidade_canonica",
                    "evidence_class", "evidence_subtype",
                )
            } | common)

    return {
        "indicators": _load_group(
            runtime,
            schema="mercado",
            table="imea_indicadores_operacionais",
            columns=INDICATOR_COLUMNS,
            order=INDICATOR_ORDER,
            rows=indicators,
            snapshot_id=snapshot_id,
        ),
        "freight_reference": _load_group(
            runtime,
            schema="logistica",
            table="imea_frete_referencia",
            columns=FREIGHT_COLUMNS,
            order=FREIGHT_ORDER,
            rows=freight,
            snapshot_id=snapshot_id,
        ),
        "crop_progress": _load_group(
            runtime,
            schema="agro",
            table="imea_progresso_cultura",
            columns=PROGRESS_COLUMNS,
            order=PROGRESS_ORDER,
            rows=progress,
            snapshot_id=snapshot_id,
        ),
        "qa": qa,
    }


def run_imea_local_file(runtime: "ZeroCostRuntime", path: str | Path) -> tuple[int, dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    started = datetime.now(timezone.utc)
    if not source.is_file():
        return 2, {
            "status": "blocked_by_quality_gate",
            "error": f"IMEA workbook local ausente: {source}",
        }

    spec = SourceSpec(
        source_id="imea_operational_xlsx",
        name="IMEA - workbook operacional autorizado local",
        group="dados",
        method="local_file",
        file_extension="xlsx",
        evidence_class="observado",
    )
    manifest = RunManifest(
        source_id=spec.source_id,
        group=spec.group,
        started_at=started.isoformat(),
        finished_at=started.isoformat(),
        status="running",
        collector_version=COLLECTOR_VERSION,
        data_coleta=started.isoformat(),
        evidence_class=spec.evidence_class,
    )
    try:
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        raw = runtime.raw.store_raw(spec, payload, digest, collected_at=started)
        parsed = parse_workbook(payload)
        load = persist_imea_parsed(
            runtime,
            parsed,
            snapshot_id=digest,
            data_coleta=started.isoformat(),
            source_hash=digest,
            raw_artifact_ref=raw.path,
        )
        qa = dict(parsed.get("qa") or {})
        finished = datetime.now(timezone.utc)
        previous = runtime.raw.load_state(spec.source_id)
        changed = previous.get("last_sha256") != digest
        manifest.finished_at = finished.isoformat()
        manifest.status = "updated" if changed else "unchanged"
        manifest.observed_url = f"local-file://{source.name}"
        manifest.raw_artifact_ref = raw.path
        manifest.sha256 = digest
        manifest.bytes_read = len(payload)
        manifest.content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        manifest.changed = changed
        manifest.records_read = int(qa.get("records") or len(parsed["records"]))
        manifest.records_accepted = len(parsed["records"])
        manifest.records_rejected = 0
        manifest.data_referencia = qa.get("last_date")
        manifest.competencia = str(qa.get("last_date"))[:7] if qa.get("last_date") else None
        manifest.extra = {
            "backend": "duckdb",
            "row_level_evidence": "mixed_observed_and_estimated",
            "qa": qa,
            "load": load,
        }
        runtime.raw.write_manifest(manifest)
        runtime.raw.save_state(spec.source_id, {
            "last_sha256": digest,
            "last_checked_at": finished.isoformat(),
            "last_raw_artifact_ref": raw.path,
            "last_source_name": source.name,
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
