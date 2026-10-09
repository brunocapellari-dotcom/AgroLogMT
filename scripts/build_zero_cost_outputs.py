from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.local_analytics_store import LocalAnalyticsStore
from models.commercial_report_builder import build_report_sections
from models.agrolog_intelligence_report import render_markdown
from models.zero_cost_snapshot import build_zero_cost_snapshot
from scripts.build_zero_cost_bundle import build_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AgroLog ZERO_COST commercial outputs from DuckDB")
    parser.add_argument("--db", default=".agrolog-zero-cost/analytics/agrolog.duckdb")
    parser.add_argument("--uf", default="MT")
    parser.add_argument("--output-dir", default="maritime_ui/public/data")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    store = LocalAnalyticsStore(args.db, Path(args.db).parent.parent / "parquet")
    snapshot = build_zero_cost_snapshot(store, uf=args.uf.upper())
    snapshot_path, bundle_manifest = build_bundle(snapshot, output_dir)

    sections = build_report_sections(snapshot)
    report_md, gate = render_markdown(sections, freshness=snapshot.get("freshness"))
    report_md_path = output_dir / "integrated-report.md"
    report_md_path.write_text(report_md, encoding="utf-8")

    report_json_path = output_dir / "integrated-report.json"
    report_json_path.write_text(
        json.dumps(
            {
                "product": "AGROLOG INTELLIGENCE",
                "delivery_mode": "ZERO_COST",
                "sellability": gate.to_dict(),
                "sections": [sections[title].to_dict() for title in sections],
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ) + "\n",
        encoding="utf-8",
    )
    gate_path = output_dir / "sellability.json"
    gate_path.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "delivery_mode": "ZERO_COST",
        "snapshot": str(snapshot_path),
        "bundle_manifest": str(bundle_manifest),
        "report_markdown": str(report_md_path),
        "report_json": str(report_json_path),
        "sellability": gate.status,
        "blockers": list(gate.blockers),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
