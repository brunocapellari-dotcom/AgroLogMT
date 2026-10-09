from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from collector.cli import load_sources
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.commercial_report_builder import build_report_sections
from models.agrolog_intelligence_report import render_markdown
from models.zero_cost_snapshot import build_zero_cost_snapshot
from scripts.build_zero_cost_bundle import build_bundle

SUPPORTED_METHODS = {"bcb_ptax_daily", "comexstat_api", "mdic_comexstat_api", "ana_hidroweb_adopted"}


def _source_by_id(config: str, source_id: str):
    for spec in load_sources(config):
        if spec.source_id == source_id:
            return spec
    raise ValueError(f"source_id não encontrado em {config}: {source_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgroLog ZERO_COST public-source pipeline")
    parser.add_argument("--root", default=".agrolog-zero-cost")
    parser.add_argument("--config", default="collector/config/sources.p0.json")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--uf", default="MT")
    parser.add_argument("--output-dir", default="maritime_ui/public/data")
    parser.add_argument("--no-collect", action="store_true")
    parser.add_argument("--no-global-public", action="store_true", help="Do not collect Argentina/WASDE public sources")
    parser.add_argument("--pilot-config", default="collector/config/sources.pilot.json")
    parser.add_argument("--no-conab", action="store_true", help="Do not collect the official CONAB crop workbook")
    parser.add_argument("--imea-file", default=os.environ.get("AGROLOG_IMEA_LOCAL_FILE"), help="Authorized local IMEA XLSX path")
    args = parser.parse_args()

    runtime = ZeroCostRuntime(args.root)
    runs = []
    if not args.no_collect:
        selected = set(args.source)
        for spec in load_sources(args.config):
            if not spec.enabled:
                continue
            if selected and spec.source_id not in selected:
                continue
            if spec.method not in SUPPORTED_METHODS:
                runs.append({
                    "source_id": spec.source_id,
                    "status": "SKIPPED_UNSUPPORTED_ZERO_COST",
                    "method": spec.method,
                })
                continue
            code, result = runtime.run_source(spec)
            runs.append({
                "source_id": spec.source_id,
                "exit_code": code,
                "status": result.get("status"),
                "result": result,
            })

        if not args.no_global_public:
            global_sources = (
                ("sagyp_argentina", runtime.run_argentina),
                ("usda_wasde", runtime.run_wasde),
            )
            for source_id, runner in global_sources:
                if selected and source_id not in selected:
                    continue
                code, result = runner()
                runs.append({
                    "source_id": source_id,
                    "exit_code": code,
                    "status": result.get("status"),
                    "result": result,
                })

        conab_source_id = "conab_safra_graos_xlsx"
        if not args.no_conab and (not selected or conab_source_id in selected):
            try:
                conab_spec = _source_by_id(args.pilot_config, conab_source_id)
                code, result = runtime.run_conab(conab_spec)
            except Exception as exc:
                code, result = 2, {
                    "status": "blocked_by_quality_gate",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            runs.append({
                "source_id": conab_source_id,
                "exit_code": code,
                "status": result.get("status"),
                "result": result,
            })

        imea_source_id = "imea_operational_xlsx"
        if args.imea_file and (not selected or imea_source_id in selected):
            code, result = runtime.run_imea_file(args.imea_file)
            runs.append({
                "source_id": imea_source_id,
                "exit_code": code,
                "status": result.get("status"),
                "result": result,
            })
        elif selected and imea_source_id in selected:
            runs.append({
                "source_id": imea_source_id,
                "exit_code": 2,
                "status": "BLOCKED_LOCAL_FILE",
                "result": {
                    "status": "BLOCKED_LOCAL_FILE",
                    "error": "Defina --imea-file ou AGROLOG_IMEA_LOCAL_FILE; Google Drive não é obrigatório no ZERO_COST.",
                },
            })

    runtime_manifest = runtime.write_runtime_manifest()
    snapshot = build_zero_cost_snapshot(runtime.analytics, uf=args.uf.upper())
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path, bundle_manifest = build_bundle(snapshot, output_dir)

    sections = build_report_sections(snapshot)
    markdown, gate = render_markdown(sections, freshness=snapshot.get("freshness"))
    report_path = output_dir / "integrated-report.md"
    report_path.write_text(markdown, encoding="utf-8")
    (output_dir / "sellability.json").write_text(
        json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    run_manifest = {
        "mode": "ZERO_COST",
        "paid_runtime_required": False,
        "cloud_credentials_required": False,
        "runs": runs,
        "snapshot_status": snapshot["status"],
        "sellability": gate.to_dict(),
        "runtime_manifest": str(runtime_manifest),
        "snapshot": str(snapshot_path),
        "bundle_manifest": str(bundle_manifest),
        "report": str(report_path),
    }
    manifest_path = Path(args.root) / "last-run.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(run_manifest, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
