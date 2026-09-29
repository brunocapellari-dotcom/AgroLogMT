#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from models.agrolog_360_marts import build_agrolog360_sql_bundle


SOURCE_DEPENDENCIES = {
    "climate_rollups": ("clima.daily_observations",),
    "storage_balance": ("agro.conab_safra_graos", "logistica.v_armazens_conab_latest"),
    "freight_lanes": ("logistica.freight_offer_observations",),
    "fertilizer_imports": ("comercio_exterior.comexstat_ncm_import",),
    "biomass": ("energia.biomass_observations",),
    "hydrology_latest": ("hidrologia.m04_components_latest",),
    "ptax_current": ("mercado.ptax_usd_daily",),
    "imea_freight_reference": ("logistica.imea_frete_referencia",),
    "overview_current": (
        "marts_agrolog360.storage_balance_v1",
        "marts_agrolog360.climate_rollups_v1",
    ),
}
SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _safe(value: str) -> str:
    if not SAFE.fullmatch(value):
        raise ValueError(f"unsafe identifier: {value!r}")
    return value


def _exists(client: bigquery.Client, project: str, short_name: str) -> bool:
    dataset, table = short_name.split(".", 1)
    try:
        client.get_table(f"{project}.{_safe(dataset)}.{_safe(table)}")
        return True
    except NotFound:
        return False


def apply_ready_marts(*, project: str, location: str, execute: bool) -> dict[str, Any]:
    project = _safe(project)
    client = bigquery.Client(project=project, location=location)
    bundle = {mart.mart_id: mart for mart in build_agrolog360_sql_bundle(project)}
    rows: list[dict[str, Any]] = []
    dataset_created = False

    for mart_id in ("climate_rollups", "storage_balance", "freight_lanes", "fertilizer_imports", "biomass", "hydrology_latest", "ptax_current", "imea_freight_reference", "overview_current"):
        mart = bundle[mart_id]
        missing = [dep for dep in SOURCE_DEPENDENCIES[mart_id] if not _exists(client, project, dep)]
        if missing:
            rows.append({"mart_id": mart_id, "status": "GATED", "missing": missing})
            continue
        if not execute:
            rows.append({"mart_id": mart_id, "status": "READY", "target": mart.target})
            continue

        if not dataset_created:
            dataset_ref = bigquery.Dataset(f"{project}.marts_agrolog360")
            dataset_ref.location = location
            client.create_dataset(dataset_ref, exists_ok=True)
            dataset_created = True

        job = client.query(mart.sql)
        job.result()
        rows.append({"mart_id": mart_id, "status": "APPLIED", "target": mart.target, "job_id": job.job_id})

    return {
        "status": "PASS",
        "project": project,
        "location": location,
        "execute": execute,
        "dataset_created": dataset_created,
        "marts": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply only dependency-ready AgroLog 360 marts")
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", default="southamerica-east1")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--out", default="outputs/agrolog360-marts-apply.json")
    args = parser.parse_args()
    report = apply_ready_marts(project=args.project, location=args.location, execute=args.execute)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "execute": report["execute"], "dataset_created": report["dataset_created"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
