from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .cli import load_sources
from .cloud_store import DriveBigQueryStore
from .comexstat_pipeline import run_comexstat_pipeline
from .conab_armazens import SOURCE_ID as CONAB_ARMAZENS_SOURCE_ID
from .conab_armazens_pipeline import run_conab_armazens_pipeline
from .conab_safra import SOURCE_ID as CONAB_SAFRA_SOURCE_ID
from .conab_safra_pipeline import run_conab_safra_pipeline
from .ibge_pipeline import SOURCE_ID as IBGE_SOURCE_ID, run_ibge_pipeline
from .imea_operational_pipeline import SOURCE_ID as IMEA_OPERATIONAL_SOURCE_ID, run_imea_operational_pipeline
from .models import SourceSpec
from .nasa_power_pipeline import SOURCE_ID as NASA_POWER_SOURCE_ID, run_nasa_power_pipeline
from .orchestrator import CollectorEngine
from .p0_pipeline import (
    ANA_SOURCE_ID,
    PTAX_SOURCE_ID,
    run_ana_hydro_pipeline,
    run_bcb_ptax_pipeline,
)
from .registry_scheduler import RegistryScheduler, ScheduledSource, scheduler_payload
from .source_registry import DataSourceRegistry


def _missing_required_env(spec: SourceSpec) -> list[str]:
    required = spec.options.get("required_env_vars", [])
    return [str(name) for name in required if not os.environ.get(str(name))]


def _execute_spec(
    spec: SourceSpec,
    store: DriveBigQueryStore,
    engine: CollectorEngine,
) -> tuple[int, dict[str, Any]]:
    if spec.source_id == CONAB_ARMAZENS_SOURCE_ID:
        return run_conab_armazens_pipeline(spec, store)
    if spec.source_id == CONAB_SAFRA_SOURCE_ID:
        return run_conab_safra_pipeline(spec, store)
    if spec.source_id == IBGE_SOURCE_ID:
        return run_ibge_pipeline(spec, store)
    if spec.source_id == NASA_POWER_SOURCE_ID:
        return run_nasa_power_pipeline(spec, store)
    if spec.source_id == IMEA_OPERATIONAL_SOURCE_ID:
        return run_imea_operational_pipeline(spec, store)
    if spec.source_id == PTAX_SOURCE_ID:
        return run_bcb_ptax_pipeline(spec, store)
    if spec.source_id == ANA_SOURCE_ID:
        return run_ana_hydro_pipeline(spec, store)
    if spec.method == "comexstat_api":
        return run_comexstat_pipeline(spec, store)

    manifest = engine.run_source(spec)
    return (1 if manifest.status == "error" else 0), manifest.to_dict()


def _blocked_env_payload(spec: SourceSpec, missing_env: list[str]) -> dict[str, Any]:
    return {
        "source_id": spec.source_id,
        "status": "blocked_missing_secure_env",
        "missing_env_vars": missing_env,
    }


def _run_scheduled_item(
    item: ScheduledSource,
    scheduler: RegistryScheduler,
    store: DriveBigQueryStore,
    engine: CollectorEngine,
) -> tuple[int, dict[str, Any]]:
    if not item.due or item.spec is None:
        return 0, {"scheduler": scheduler_payload(item), "status": "skipped"}

    missing_env = _missing_required_env(item.spec)
    if missing_env:
        payload = _blocked_env_payload(item.spec, missing_env)
        scheduler.record_result(item, status="blocked_missing_secure_env", error="missing secure environment")
        return 1, {"scheduler": scheduler_payload(item), "result": payload}

    code, payload = _execute_spec(item.spec, store, engine)
    status = str(payload.get("status") or ("error" if code else "ok"))
    scheduler.record_result(
        item,
        status="error" if code else status,
        error=str(payload.get("error") or "") if code else None,
    )
    return code, {"scheduler": scheduler_payload(item), "result": payload}


def _run_registry_mode(store: DriveBigQueryStore, engine: CollectorEngine) -> int:
    registry_path = Path(
        os.environ.get(
            "AGROLOG_SOURCE_REGISTRY",
            "/app/collector/config/data_source_registry.v1.json",
        )
    )
    registry_source_id = os.environ.get("AGROLOG_SOURCE_ID") or None
    domain = os.environ.get("AGROLOG_DOMAIN") or None
    wake_sources = {
        value.strip()
        for value in os.environ.get("AGROLOG_WAKE_SOURCE_IDS", "").split(",")
        if value.strip()
    }

    registry = DataSourceRegistry.load(registry_path)
    scheduler = RegistryScheduler(registry, store, repo_root=Path("/app"))
    plan = scheduler.plan(
        source_id=registry_source_id,
        domain=domain,
        wake_sources=wake_sources,
    )
    if not plan:
        raise SystemExit(f"Registry scheduler sem fontes para source_id={registry_source_id!r} domain={domain!r}")

    failed = 0
    executed = 0
    for item in plan:
        if not item.due:
            print(json.dumps({"scheduler": scheduler_payload(item), "status": "skipped"}, ensure_ascii=False, sort_keys=True), flush=True)
            if item.reason == "execution_not_implemented":
                failed += 1
            continue

        executed += 1
        code, result = _run_scheduled_item(item, scheduler, store, engine)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if code:
            failed += 1
            # Fallback is collected as independent evidence. It never overwrites
            # or relabels the failed primary source.
            for fallback in scheduler.fallback_candidates(item):
                if not fallback.due:
                    print(json.dumps({
                        "fallback_for": item.registry_source_id,
                        "scheduler": scheduler_payload(fallback),
                        "status": "fallback_not_runnable",
                    }, ensure_ascii=False, sort_keys=True), flush=True)
                    continue
                fb_code, fb_result = _run_scheduled_item(fallback, scheduler, store, engine)
                print(json.dumps({
                    "fallback_for": item.registry_source_id,
                    **fb_result,
                }, ensure_ascii=False, sort_keys=True), flush=True)
                # Primary remains failed even when fallback evidence succeeds.
                if fb_code:
                    failed += 1

    print(json.dumps({
        "registry_scheduler_summary": {
            "planned": len(plan),
            "executed": executed,
            "failed": failed,
            "source_id": registry_source_id,
            "domain": domain,
        }
    }, ensure_ascii=False, sort_keys=True), flush=True)
    return 1 if failed else 0


def _run_legacy_mode(store: DriveBigQueryStore, engine: CollectorEngine) -> int:
    config = os.environ.get("AGROLOG_CONFIG", "/app/collector/config/sources.pilot.json")
    group = os.environ.get("AGROLOG_GROUP")
    source_id = os.environ.get("AGROLOG_SOURCE_ID")
    specs = load_sources(Path(config))
    selected = [
        spec for spec in specs
        if spec.enabled and (not group or spec.group == group) and (not source_id or spec.source_id == source_id)
    ]
    if not selected:
        raise SystemExit(f"Nenhuma fonte habilitada para group={group!r} source_id={source_id!r}")

    failed = 0
    for spec in selected:
        missing_env = _missing_required_env(spec)
        if missing_env:
            payload = _blocked_env_payload(spec, missing_env)
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
            if source_id:
                failed += 1
            continue
        code, payload = _execute_spec(spec, store, engine)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
        if code:
            failed += 1
    return 1 if failed else 0


def main() -> int:
    store = DriveBigQueryStore()
    engine = CollectorEngine(store=store)  # type: ignore[arg-type]
    registry_mode = os.environ.get("AGROLOG_REGISTRY_MODE", "0").strip() == "1"
    if registry_mode:
        return _run_registry_mode(store, engine)
    return _run_legacy_mode(store, engine)


if __name__ == "__main__":
    raise SystemExit(main())
