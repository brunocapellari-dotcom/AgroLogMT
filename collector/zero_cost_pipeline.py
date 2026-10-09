from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .comexstat_pipeline import normalize_comex_response
from .adapters import ComexStatApiAdapter
from .local_analytics_store import LocalAnalyticsStore
from .models import RunManifest, SourceSpec
from .orchestrator import COLLECTOR_VERSION, CollectorEngine
from .p0_adapters import BcbPtaxDailyAdapter
from .storage import LocalStore, sha256_bytes
from .zero_cost_conab import run_conab_source
from .zero_cost_public_sources import run_ana_source, run_argentina_source, run_wasde_source

PTAX_COLUMNS = {
    "data_referencia": "DATE NOT NULL",
    "data_publicacao": "TIMESTAMP",
    "data_coleta": "TIMESTAMP NOT NULL",
    "competencia": "VARCHAR NOT NULL",
    "moeda": "VARCHAR NOT NULL",
    "cotacao_compra": "DOUBLE NOT NULL",
    "cotacao_venda": "DOUBLE NOT NULL",
    "data_hora_cotacao": "TIMESTAMP NOT NULL",
    "source_url": "VARCHAR NOT NULL",
    "snapshot_sha256": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
    "evidence_class": "VARCHAR NOT NULL",
    "collector_version": "VARCHAR NOT NULL",
}
PTAX_COLUMN_ORDER = list(PTAX_COLUMNS)

COMEX_COLUMNS = {
    "snapshot_id": "VARCHAR NOT NULL",
    "record_id": "VARCHAR NOT NULL",
    "data_referencia": "DATE NOT NULL",
    "competencia": "VARCHAR NOT NULL",
    "flow": "VARCHAR NOT NULL",
    "ncm_code": "VARCHAR NOT NULL",
    "ncm_name": "VARCHAR",
    "state_filter_id": "VARCHAR",
    "state_name": "VARCHAR NOT NULL",
    "country_code": "VARCHAR",
    "country_name": "VARCHAR",
    "via_code": "VARCHAR",
    "via_name": "VARCHAR",
    "urf_code": "VARCHAR",
    "urf_name": "VARCHAR",
    "kg_liquido": "BIGINT NOT NULL",
    "valor_fob_usd": "BIGINT NOT NULL",
    "data_publicacao": "DATE",
    "data_coleta": "TIMESTAMP NOT NULL",
    "source_url": "VARCHAR",
    "source_hash": "VARCHAR NOT NULL",
    "raw_artifact_ref": "VARCHAR",
    "evidence_class": "VARCHAR NOT NULL",
    "collector_version": "VARCHAR NOT NULL",
}
COMEX_COLUMN_ORDER = list(COMEX_COLUMNS)


class ZeroCostRuntime:
    def __init__(self, root: str | Path = ".agrolog-zero-cost") -> None:
        self.root = Path(root)
        self.raw = LocalStore(self.root / "collector")
        self.analytics = LocalAnalyticsStore(
            self.root / "analytics" / "agrolog.duckdb",
            self.root / "parquet",
        )

    def _ptax_engine(self) -> CollectorEngine:
        def resolver(method: str):
            if method == "bcb_ptax_daily":
                return BcbPtaxDailyAdapter()
            from .adapters import get_adapter
            return get_adapter(method)

        return CollectorEngine(store=self.raw, adapter_resolver=resolver)

    def persist_ptax_capture(self, spec: SourceSpec, manifest: RunManifest, payload: bytes) -> dict[str, Any]:
        body = json.loads(payload.decode("utf-8"))
        row = body["latest"]
        timestamp = str(row["dataHoraCotacao"])
        data_ref = timestamp[:10]
        self.analytics.ensure_table("mercado", "ptax_usd_daily", PTAX_COLUMNS)
        existing = self.analytics.scalar(
            """
            SELECT COUNT(*) FROM mercado.ptax_usd_daily
            WHERE data_referencia=? AND data_hora_cotacao=?
            """,
            [data_ref, timestamp],
        )
        inserted = 0
        if not existing:
            normalized = {
                "data_referencia": data_ref,
                "data_publicacao": timestamp,
                "data_coleta": manifest.data_coleta,
                "competencia": data_ref[:7],
                "moeda": "USD",
                "cotacao_compra": float(row["cotacaoCompra"]),
                "cotacao_venda": float(row["cotacaoVenda"]),
                "data_hora_cotacao": timestamp,
                "source_url": manifest.observed_url,
                "snapshot_sha256": manifest.sha256,
                "raw_artifact_ref": manifest.raw_artifact_ref,
                "evidence_class": "observado",
                "collector_version": manifest.collector_version,
            }
            inserted = self.analytics.insert_rows(
                "mercado", "ptax_usd_daily", [normalized], columns=PTAX_COLUMN_ORDER
            )
        parquet = self.analytics.export_table_parquet("mercado", "ptax_usd_daily")
        return {
            "table": "mercado.ptax_usd_daily",
            "inserted": inserted,
            "duplicate": bool(existing),
            "parquet": str(parquet),
            "data_referencia": data_ref,
        }

    def run_ptax(self, spec: SourceSpec) -> tuple[int, dict[str, Any]]:
        outcome = self._ptax_engine().run_source_capture(spec)
        manifest = outcome.manifest
        if manifest.status == "error" or outcome.payload is None or not manifest.sha256:
            return 1, {"status": "source_error", "acquisition": manifest.to_dict()}
        try:
            load = self.persist_ptax_capture(spec, manifest, outcome.payload)
            return 0, {"status": "ok", "acquisition": manifest.to_dict(), "load": load}
        except Exception as exc:
            return 2, {
                "status": "blocked_by_quality_gate",
                "acquisition": manifest.to_dict(),
                "error": f"{type(exc).__name__}: {exc}",
            }

    def persist_comex_rows(self, rows: list[dict[str, Any]], snapshot_id: str) -> dict[str, Any]:
        if not rows:
            raise ValueError("Comex local loader recusou lote vazio")
        self.analytics.ensure_table("comercio_exterior", "comexstat_trade_monthly", COMEX_COLUMNS)
        existing = int(self.analytics.scalar(
            "SELECT COUNT(*) FROM comercio_exterior.comexstat_trade_monthly WHERE snapshot_id=?",
            [snapshot_id],
        ) or 0)
        if existing:
            expected_records = len(rows)
            expected_kg = sum(int(row["kg_liquido"]) for row in rows)
            expected_fob = sum(int(row["valor_fob_usd"]) for row in rows)
            actual = self.analytics.query(
                """
                SELECT COUNT(*) records, COALESCE(SUM(kg_liquido),0) kg,
                       COALESCE(SUM(valor_fob_usd),0) fob
                FROM comercio_exterior.comexstat_trade_monthly
                WHERE snapshot_id=?
                """,
                [snapshot_id],
            )[0]
            if (int(actual["records"]), int(actual["kg"]), int(actual["fob"])) != (
                expected_records, expected_kg, expected_fob
            ):
                raise RuntimeError("Tie-out Comex local falhou para snapshot já persistido")
            inserted = 0
        else:
            inserted = self.analytics.insert_rows(
                "comercio_exterior",
                "comexstat_trade_monthly",
                rows,
                columns=COMEX_COLUMN_ORDER,
            )
        parquet = self.analytics.export_table_parquet("comercio_exterior", "comexstat_trade_monthly")
        return {
            "table": "comercio_exterior.comexstat_trade_monthly",
            "snapshot_id": snapshot_id,
            "inserted": inserted,
            "records_existing": existing,
            "parquet": str(parquet),
        }

    def run_comex(self, spec: SourceSpec) -> tuple[int, dict[str, Any]]:
        started = datetime.now(timezone.utc)
        manifest = RunManifest(
            source_id=spec.source_id,
            group=spec.group,
            started_at=started.isoformat(),
            finished_at=started.isoformat(),
            status="running",
            collector_version=COLLECTOR_VERSION,
            data_coleta=started.isoformat(),
            evidence_class="observado",
        )
        raw_ref = None
        digest = None
        try:
            result = ComexStatApiAdapter().fetch(spec)
            collected = datetime.now(timezone.utc)
            digest = sha256_bytes(result.payload)
            state = self.raw.load_state(spec.source_id)
            changed = state.get("last_sha256") != digest
            raw = self.raw.store_raw(spec, result.payload, digest, collected_at=collected)
            raw_ref = raw.path
            body = json.loads(result.payload.decode("utf-8"))
            competence, rows = normalize_comex_response(
                body,
                spec=spec,
                snapshot_id=digest,
                data_coleta=collected.isoformat(),
                data_publicacao=result.last_modified,
                source_url=result.observed_url,
                raw_artifact_ref=raw.path,
            )
            load = self.persist_comex_rows(rows, digest)
            finished = datetime.now(timezone.utc)
            manifest.finished_at = finished.isoformat()
            manifest.status = "updated" if changed else "unchanged"
            manifest.data_coleta = collected.isoformat()
            manifest.observed_url = result.observed_url
            manifest.raw_artifact_ref = raw.path
            manifest.sha256 = digest
            manifest.bytes_read = len(result.payload)
            manifest.content_type = result.content_type
            manifest.last_modified = result.last_modified
            manifest.changed = changed
            manifest.records_read = len(rows)
            manifest.records_accepted = len(rows)
            manifest.records_rejected = 0
            manifest.data_referencia = f"{competence}-01"
            manifest.data_publicacao = result.last_modified[:10] if result.last_modified else None
            manifest.competencia = competence
            manifest.extra = {"load": load, "backend": "duckdb"}
            self.raw.write_manifest(manifest)
            self.raw.save_state(
                spec.source_id,
                {
                    "last_sha256": digest,
                    "competencia": competence,
                    "last_checked_at": finished.isoformat(),
                    "last_raw_artifact_ref": raw.path,
                    "analytical_backend": "duckdb",
                },
            )
            return 0, {"status": "ok", "acquisition": manifest.to_dict(), "load": load}
        except Exception as exc:
            manifest.finished_at = datetime.now(timezone.utc).isoformat()
            manifest.status = "error"
            manifest.raw_artifact_ref = raw_ref
            manifest.sha256 = digest
            manifest.error = f"{type(exc).__name__}: {exc}"
            try:
                self.raw.write_manifest(manifest)
            except Exception:
                pass
            return 2, {"status": "blocked_by_quality_gate", "acquisition": manifest.to_dict()}

    def run_source(self, spec: SourceSpec) -> tuple[int, dict[str, Any]]:
        if spec.method == "bcb_ptax_daily":
            return self.run_ptax(spec)
        if spec.method in {"comexstat_api", "mdic_comexstat_api"}:
            return self.run_comex(spec)
        if spec.method == "ana_hidroweb_adopted":
            return run_ana_source(self, spec)
        return 3, {
            "status": "unsupported_zero_cost_normalizer",
            "source_id": spec.source_id,
            "method": spec.method,
        }

    def run_argentina(self) -> tuple[int, dict[str, Any]]:
        return run_argentina_source(self)

    def run_wasde(self) -> tuple[int, dict[str, Any]]:
        return run_wasde_source(self)

    def run_conab(self, spec: SourceSpec) -> tuple[int, dict[str, Any]]:
        return run_conab_source(self, spec)

    def write_runtime_manifest(self) -> Path:
        return self.analytics.write_manifest(self.root / "runtime-manifest.json")
