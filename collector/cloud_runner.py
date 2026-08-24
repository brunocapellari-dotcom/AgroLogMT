from __future__ import annotations

import json
import os
from pathlib import Path

from .cli import load_sources
from .cloud_store import DriveBigQueryStore
from .conab_armazens import SOURCE_ID as CONAB_ARMAZENS_SOURCE_ID
from .conab_armazens_pipeline import run_conab_armazens_pipeline
from .conab_safra import SOURCE_ID as CONAB_SAFRA_SOURCE_ID
from .conab_safra_pipeline import run_conab_safra_pipeline
from .ibge_pipeline import SOURCE_ID as IBGE_SOURCE_ID, run_ibge_pipeline
from .imea_operational_pipeline import SOURCE_ID as IMEA_OPERATIONAL_SOURCE_ID, run_imea_operational_pipeline
from .nasa_power_pipeline import SOURCE_ID as NASA_POWER_SOURCE_ID, run_nasa_power_pipeline
from .orchestrator import CollectorEngine


def main() -> int:
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

    store = DriveBigQueryStore()
    engine = CollectorEngine(store=store)  # type: ignore[arg-type]
    failed = 0
    for spec in selected:
        if spec.source_id == CONAB_ARMAZENS_SOURCE_ID:
            code, payload = run_conab_armazens_pipeline(spec, store)
        elif spec.source_id == CONAB_SAFRA_SOURCE_ID:
            code, payload = run_conab_safra_pipeline(spec, store)
        elif spec.source_id == IBGE_SOURCE_ID:
            code, payload = run_ibge_pipeline(spec, store)
        elif spec.source_id == NASA_POWER_SOURCE_ID:
            code, payload = run_nasa_power_pipeline(spec, store)
        elif spec.source_id == IMEA_OPERATIONAL_SOURCE_ID:
            code, payload = run_imea_operational_pipeline(spec, store)
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
