#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from models.intermediate_marts import build_sql_bundle


REQUIRED_SOURCE_MAP = {
    "soy_mt_production": ("agro.conab_safra_graos",),
    "soy_mt_storage": ("logistica.armazens_conab", "referencia.municipios_ibge"),
    "soy_mt_market": ("mercado.imea_indicadores_operacionais",),
    "soy_mt_trade": ("comercio_exterior.comexstat_ncm_export",),
}


def _source_ready(inventory: dict[str, dict[str, Any]], table: str) -> tuple[bool, list[str]]:
    meta = inventory.get(table, {})
    reasons: list[str] = []
    if not meta.get("exists"):
        reasons.append("missing")
    if meta.get("qa_status") != "pass":
        reasons.append("qa_not_pass")
    if not meta.get("point_in_time_ready"):
        reasons.append("point_in_time_not_ready")
    return not reasons, reasons


def main() -> int:
    ap = argparse.ArgumentParser(description="Planeja marts intermediários Soja MT usando evidência real do BigQuery inspector")
    ap.add_argument("--project", required=True)
    ap.add_argument("--readiness", required=True)
    ap.add_argument("--trade-codes", default="contracts/product_trade_codes.v1.json")
    ap.add_argument("--climate-source", default="clima.nasa_power_daily")
    ap.add_argument("--out", default="soy_mt_intermediate_marts_plan.json")
    args = ap.parse_args()

    readiness = json.loads(Path(args.readiness).read_text(encoding="utf-8"))
    inventory = readiness.get("inventory", {})
    codes = json.loads(Path(args.trade_codes).read_text(encoding="utf-8"))
    soybean_codes = tuple(codes["products"]["soja_grao"]["ncm8"])
    bundle = build_sql_bundle(args.project, soybean_ncm_codes=soybean_codes, climate_source=args.climate_source)

    plan: list[dict[str, Any]] = []
    for item in bundle:
        if item.mart_id == "soy_mt_climate":
            required = (args.climate_source,)
        else:
            required = REQUIRED_SOURCE_MAP[item.mart_id]
        failures: list[str] = []
        for table in required:
            ready, reasons = _source_ready(inventory, table)
            if not ready:
                failures.append(f"{table}:" + ",".join(reasons))
        plan.append({
            **item.to_dict(),
            "source_tables": list(required),
            "ready": not failures,
            "failures": failures,
            "execution_policy": "execute only after ready=true; planner itself is read-only",
        })

    payload = {
        "project": args.project,
        "read_only": True,
        "all_ready": all(row["ready"] for row in plan),
        "ready_count": sum(row["ready"] for row in plan),
        "total": len(plan),
        "marts": plan,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if payload["all_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
