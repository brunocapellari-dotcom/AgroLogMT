from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.cli import load_sources
from collector.zero_cost_pipeline import ZeroCostRuntime
from collector.zero_cost_freight import load_freight_input, persist_freight_records
from collector.zero_cost_market import (
    ALLOWED_USAGE_RIGHTS,
    MarketAuthorization,
    load_market_input,
    persist_market_references,
)
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
    parser.add_argument("--no-weather", action="store_true", help="Do not collect NOAA GFS weather horizons")
    parser.add_argument("--pilot-config", default="collector/config/sources.pilot.json")
    parser.add_argument("--no-conab", action="store_true", help="Do not collect the official CONAB crop workbook")
    parser.add_argument("--freight-input", help="Authorized freight JSON/JSONL input")
    parser.add_argument("--market-input", help="Authorized market CSV/JSON/JSONL input")
    parser.add_argument("--market-source-id")
    parser.add_argument("--market-source-name")
    parser.add_argument("--market-usage-rights", choices=sorted(ALLOWED_USAGE_RIGHTS))
    parser.add_argument("--market-authorization-basis")
    args = parser.parse_args()

    if args.market_input:
        required_market_args = {
            "--market-source-id": args.market_source_id,
            "--market-source-name": args.market_source_name,
            "--market-usage-rights": args.market_usage_rights,
            "--market-authorization-basis": args.market_authorization_basis,
        }
        missing = [name for name, value in required_market_args.items() if not value]
        if missing:
            parser.error(
                "--market-input requires explicit source/rights metadata: "
                + ", ".join(missing)
            )

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

        gfs_source_id = "gfs_nomads"
        if not args.no_weather and (not selected or gfs_source_id in selected):
            code, result = runtime.run_gfs()
            runs.append({
                "source_id": gfs_source_id,
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

    if args.freight_input:
        try:
            freight_rows = load_freight_input(args.freight_input)
            freight_result = persist_freight_records(runtime, freight_rows)
            runs.append({
                "source_id": "authorized_freight_input",
                "exit_code": 0,
                "status": "ok",
                "result": freight_result,
            })
        except Exception as exc:
            runs.append({
                "source_id": "authorized_freight_input",
                "exit_code": 2,
                "status": "blocked_by_quality_gate",
                "result": {"error": f"{type(exc).__name__}: {exc}"},
            })

    if args.market_input:
        try:
            authorization = MarketAuthorization(
                source_id=str(args.market_source_id),
                source_name=str(args.market_source_name),
                usage_rights=str(args.market_usage_rights),
                authorization_basis=str(args.market_authorization_basis),
            )
            market_rows = load_market_input(args.market_input)
            market_result = persist_market_references(
                runtime,
                market_rows,
                authorization=authorization,
            )
            runs.append({
                "source_id": authorization.source_id,
                "exit_code": 0,
                "status": "ok",
                "result": market_result,
            })
        except Exception as exc:
            runs.append({
                "source_id": str(args.market_source_id or "authorized_market_input"),
                "exit_code": 2,
                "status": "blocked_by_quality_gate",
                "result": {"error": f"{type(exc).__name__}: {exc}"},
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
    return 0 if gate.status == "SELLABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
