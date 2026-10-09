#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from collector.source_registry import DataSourceRegistry


PRIORITY_SOURCE_IDS = (
    "conab_armazens_cadastrados",
    "conab_safra_graos_xlsx",
    "ibge_pam",
    "imea_operational_xlsx",
    "mdic_comexstat",
    "bcb_ptax_usd_daily",
    "ana_hidroweb",
    "inmet_weather",
    "cptec_weather",
    "antt_open_data",
    "antt_rntrc",
    "antt_mdfe_public",
    "antaq_operational",
    "aisstream_maritime",
    "official_port_lineups",
    "whatsapp_freight_authorized",
    "anp_diesel",
    "epe_sienergia_biomass",
    "ibge_pevs_biomass",
    "snif_forest_biomass",
    "sema_mt_sisflora",
    "ons_biomass_generation",
    "epe_ben_biomass",
    "anp_biometano",
    "ibama_dof_native",
)


def build_readiness(repo: Path) -> dict[str, Any]:
    registry = DataSourceRegistry.load(repo / "collector/config/data_source_registry.v1.json")
    rows = []
    for source_id in PRIORITY_SOURCE_IDS:
        entry = registry.get(source_id)
        execution_exists = None
        if entry.execution_ref:
            file_part = str(entry.execution_ref).split("#", 1)[0]
            execution_exists = (repo / file_part).exists()
        rows.append({
            "source_id": source_id,
            "domain": entry.domain,
            "status": entry.status,
            "trusted_transport": entry.trusted_transport,
            "execution_ref": entry.execution_ref,
            "execution_exists": execution_exists,
            "ready_for_scheduler": entry.status == "active" and (entry.endpoint is not None or bool(entry.execution_ref)),
        })
    return {
        "status": "PASS",
        "priority_sources": len(rows),
        "active": sum(1 for row in rows if row["status"] == "active"),
        "gated": sum(1 for row in rows if row["status"] == "gated"),
        "planned": sum(1 for row in rows if row["status"] == "planned"),
        "sources": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AgroLog 360 source readiness inventory")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--out", default="outputs/agrolog360-source-readiness.json")
    args = parser.parse_args()
    report = build_readiness(Path(args.repo).resolve())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("status", "priority_sources", "active", "gated", "planned")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
