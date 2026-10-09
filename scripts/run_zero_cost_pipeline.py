from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.cli import load_sources
from collector.zero_cost_pipeline import ZeroCostRuntime
from models.commercial_report_builder import build_report_sections
from models.agrolog_intelligence_report import render_markdown
from models.zero_cost_snapshot import build_zero_cost_snapshot
from scripts.build_zero_cost_bundle import build_bundle

SUPPORTED_METHODS = {"bcb_ptax_daily", "comexstat_api", "mdic_comexstat_api", "ana_hidroweb_adopted"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgroLog ZERO_COST public-source pipeline")
    parser.add_argument("--root", default=".agrolog-zero-cost")
    parser.add_argument("--config", default="collector/config/sources.p0.json")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--uf", default="MT")
    parser.add_argument("--output-dir", default="maritime_ui/public/data")
    parser.add_argument("--no-collect", action="store_true")
    parser.add_argument("--no-global-public", action="store_true", help="Do not collect CONAB/Argentina/WASDE public sources")
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
                ("conab_safra_graos_xlsx", runtime.run_conab_safra),
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
