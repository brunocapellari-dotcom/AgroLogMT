from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.cli import load_sources
from collector.cloud_store import DriveBigQueryStore
from collector.conab_armazens import SOURCE_ID
from collector.conab_armazens_pipeline import run_conab_armazens_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="CONAB Armazens: RAW -> parse -> BigQuery canonico")
    parser.add_argument("--config", default="collector/config/sources.pilot.json")
    args = parser.parse_args()

    specs = load_sources(Path(args.config))
    spec = next((item for item in specs if item.source_id == SOURCE_ID), None)
    if spec is None:
        raise SystemExit(f"Fonte {SOURCE_ID!r} ausente em {args.config}")

    code, payload = run_conab_armazens_pipeline(spec, DriveBigQueryStore())
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
