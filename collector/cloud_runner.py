from __future__ import annotations

import json
import os
from pathlib import Path

from .cli import load_sources
from .cloud_store import DriveBigQueryStore
from .orchestrator import CollectorEngine


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
        manifest = engine.run_source(spec)
        print(json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True), flush=True)
        if manifest.status == "error":
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
