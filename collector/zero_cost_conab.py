from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from .adapters import get_adapter
from .conab_safra_history import discover_publications
from .conab_safra_pipeline import build_canonical_rows
from .models import SourceSpec
from .storage import sha256_bytes

if TYPE_CHECKING:
    from .zero_cost_pipeline import ZeroCostRuntime


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
    "quality_score": "DOUBLE NOT NULL",
    "quality_flags_json": "VARCHAR NOT NULL",
    "source_sheet": "VARCHAR NOT NULL",
    "source_row": "BIGINT NOT NULL",
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
    "collector_version": "VARCHAR NOT NULL",
    "parser_version": "VARCHAR NOT NULL",
}
CONAB_ORDER = list(CONAB_COLUMNS)


def _local_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["quality_flags_json"] = json.dumps(out.pop("quality_flags", []), ensure_ascii=False, sort_keys=True)
    return out


def persist_conab_rows(
    runtime: "ZeroCostRuntime",
    rows: list[dict[str, Any]],
    *,
    snapshot_id: str,
) -> dict[str, Any]:
    if not rows:
        raise ValueError("CONAB local loader recusou lote vazio")

    runtime.analytics.ensure_table("agro", "conab_safra", CONAB_COLUMNS)
    existing = int(
        runtime.analytics.scalar(
            "SELECT COUNT(*) FROM agro.conab_safra WHERE snapshot_id=?",
            [snapshot_id],
        )
        or 0
    )
    normalized = [_local_row(row) for row in rows]

    if existing:
        actual = runtime.analytics.query(
            """
            SELECT
              COUNT(*) AS records,
              COALESCE(SUM(producao_mil_t),0) AS production,
              COALESCE(SUM(area_mil_ha),0) AS area
            FROM agro.conab_safra
            WHERE snapshot_id=?
            """,
            [snapshot_id],
        )[0]
        expected_records = len(normalized)
        expected_production = sum(float(row["producao_mil_t"]) for row in normalized)
        expected_area = sum(float(row["area_mil_ha"]) for row in normalized)
        if int(actual["records"]) != expected_records:
            raise RuntimeError("Tie-out CONAB local falhou: contagem divergente")
        if abs(float(actual["production"]) - expected_production) > 1e-6:
            raise RuntimeError("Tie-out CONAB local falhou: produção divergente")
        if abs(float(actual["area"]) - expected_area) > 1e-6:
            raise RuntimeError("Tie-out CONAB local falhou: área divergente")
        inserted = 0
    else:
        inserted = runtime.analytics.insert_rows(
            "agro",
            "conab_safra",
            normalized,
            columns=CONAB_ORDER,
        )

    parquet = runtime.analytics.export_table_parquet("agro", "conab_safra")
    return {
        "table": "agro.conab_safra",
        "snapshot_id": snapshot_id,
        "records": len(normalized),
        "inserted": inserted,
        "records_existing": existing,
        "parquet": str(parquet),
    }


def run_conab_safra(runtime: "ZeroCostRuntime") -> tuple[int, dict[str, Any]]:
    try:
        publications = discover_publications(max_items=1)
        if not publications:
            raise RuntimeError("CONAB não publicou levantamento descobrível")
        publication = publications[0]

        spec = SourceSpec(
            source_id="conab_safra_graos_xlsx",
            name="CONAB - Safra de Grãos",
            group="dados",
            method="http",
            enabled=True,
            url=publication.attachment_url,
            expected_frequency="monthly",
            file_extension="xlsx",
            evidence_class="estimado",
            options={
                "allowed_hosts": ["www.gov.br"],
                "timeout_seconds": 90,
                "max_response_bytes": 128 * 1024 * 1024,
            },
        )
        result = get_adapter("http").fetch(spec)
        collected = datetime.now(timezone.utc)
        digest = sha256_bytes(result.payload)
        raw = runtime.raw.store_raw(spec, result.payload, digest, collected_at=collected)

        verified_publication = bool(publication.data_publicacao and publication.availability_basis)
        rows, stats = build_canonical_rows(
            result.payload,
            snapshot_id=digest,
            data_coleta=collected.isoformat(),
            raw_artifact_ref=raw.path,
            observed_url=result.observed_url,
            last_modified=result.last_modified,
            publication_override=publication.data_publicacao if verified_publication else None,
            availability_verified=verified_publication,
            availability_basis=publication.availability_basis,
        )
        if not rows:
            raise RuntimeError("CONAB retornou zero registros normalizados")
        if stats.get("current_quality_flagged"):
            raise RuntimeError(
                "CONAB bloqueado por quality gate: "
                f"{stats['current_quality_flagged']} registros current com flags materiais"
            )

        load = persist_conab_rows(runtime, rows, snapshot_id=digest)
        state = runtime.raw.load_state(spec.source_id)
        changed = state.get("last_sha256") != digest
        runtime.raw.save_state(
            spec.source_id,
            {
                "last_sha256": digest,
                "last_checked_at": collected.isoformat(),
                "last_raw_artifact_ref": raw.path,
                "analytical_backend": "duckdb",
                "safra": publication.safra,
                "levantamento": publication.levantamento,
                "data_publicacao": publication.data_publicacao,
            },
        )
        return 0, {
            "status": "ok",
            "source_id": spec.source_id,
            "changed": changed,
            "safra": publication.safra,
            "levantamento": publication.levantamento,
            "data_publicacao": publication.data_publicacao,
            "availability_basis": publication.availability_basis,
            "observed_url": result.observed_url,
            "sha256": digest,
            "raw_artifact_ref": raw.path,
            "parsing": stats,
            "load": load,
        }
    except Exception as exc:
        return 2, {
            "status": "blocked_by_quality_gate",
            "source_id": "conab_safra_graos_xlsx",
            "error": f"{type(exc).__name__}: {exc}",
        }
