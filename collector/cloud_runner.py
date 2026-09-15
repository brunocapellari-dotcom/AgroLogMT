from __future__ import annotations

import json
import os
from pathlib import Path

from .cli import load_sources
from .cloud_store import DriveBigQueryStore
from .comexstat_pipeline import run_comexstat_pipeline
from .conab_armazens import SOURCE_ID as CONAB_ARMAZENS_SOURCE_ID
from .conab_armazens_pipeline import run_conab_armazens_pipeline
from .conab_safra import SOURCE_ID as CONAB_SAFRA_SOURCE_ID
from .conab_safra_pipeline import run_conab_safra_pipeline
from .ibge_pipeline import SOURCE_ID as IBGE_SOURCE_ID, run_ibge_pipeline
from .ibge_ppm import SOURCE_ID as IBGE_PPM_SOURCE_ID
from .ibge_ppm_pipeline import run_ibge_ppm_pipeline
from .ibge_slaughter import SOURCE_ID as IBGE_SLAUGHTER_SOURCE_ID
from .ibge_slaughter_pipeline import run_ibge_slaughter_pipeline
from .imea_operational_pipeline import SOURCE_ID as IMEA_OPERATIONAL_SOURCE_ID, run_imea_operational_pipeline
from .mapa_sigsif import SOURCE_ID as MAPA_SIGSIF_SOURCE_ID
from .mapa_sigsif_pipeline import run_mapa_sigsif_pipeline
from .nasa_power_pipeline import SOURCE_ID as NASA_POWER_SOURCE_ID, run_nasa_power_pipeline
from .orchestrator import CollectorEngine
from .p0_pipeline import (
    ANA_SOURCE_ID,
    PTAX_SOURCE_ID,
    run_ana_hydro_pipeline,
    run_bcb_ptax_pipeline,
)


def _missing_required_env(spec) -> list[str]:
    required = spec.options.get("required_env_vars", [])
    return [str(name) for name in required if not os.environ.get(str(name))]


def main() -> int:
    config = os.environ.get("AGROLOG_CONFIG", "/app/collector/config/sources.pilot.json")
    group = os.environ.get("AGROLOG_GROUP")
    source_id = os.environ.get("AGROLOG_SOURCE_ID")
    specs = load_sources(Path(config))
    selected = [spec for spec in specs if spec.enabled and (not group or spec.group == group) and (not source_id or spec.source_id == source_id)]
    if not selected:
        raise SystemExit(f"Nenhuma fonte habilitada para group={group!r} source_id={source_id!r}")
    store = DriveBigQueryStore()
    engine = CollectorEngine(store=store)  # type: ignore[arg-type]
    failed = 0
    for spec in selected:
        missing_env = _missing_required_env(spec)
        if missing_env:
            payload = {
                "source_id": spec.source_id,
                "status": "blocked_missing_secure_env",
                "missing_env_vars": missing_env,
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
            if source_id:
                failed += 1
            continue
        if spec.source_id == CONAB_ARMAZENS_SOURCE_ID:
            code, payload = run_conab_armazens_pipeline(spec, store)
        elif spec.source_id == CONAB_SAFRA_SOURCE_ID:
            code, payload = run_conab_safra_pipeline(spec, store)
        elif spec.source_id == IBGE_SOURCE_ID:
            code, payload = run_ibge_pipeline(spec, store)
        elif spec.source_id == IBGE_PPM_SOURCE_ID:
            code, payload = run_ibge_ppm_pipeline(spec, store)
        elif spec.source_id == IBGE_SLAUGHTER_SOURCE_ID:
            code, payload = run_ibge_slaughter_pipeline(spec, store)
        elif spec.source_id == MAPA_SIGSIF_SOURCE_ID:
            code, payload = run_mapa_sigsif_pipeline(spec, store)
        elif spec.source_id == NASA_POWER_SOURCE_ID:
            code, payload = run_nasa_power_pipeline(spec, store)
        elif spec.source_id == IMEA_OPERATIONAL_SOURCE_ID:
            code, payload = run_imea_operational_pipeline(spec, store)
        elif spec.source_id == PTAX_SOURCE_ID:
            code, payload = run_bcb_ptax_pipeline(spec, store)
        elif spec.source_id == ANA_SOURCE_ID:
            code, payload = run_ana_hydro_pipeline(spec, store)
        elif spec.method == "comexstat_api":
            code, payload = run_comexstat_pipeline(spec, store)
        else:
            manifest = engine.run_source(spec)
            print(json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True), flush=True)
            if manifest.status == "error":
                failed += 1
            continue
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)
        if code:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
