#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from models.agrolog_intelligence_report import render_markdown
from models.commercial_report_builder import build_report_sections


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Relatório Integrado AgroLog from a commercial snapshot.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--out", default="outputs/AGROLOG_INTELLIGENCE.md")
    parser.add_argument("--gate-out", default="outputs/AGROLOG_INTELLIGENCE_GATE.json")
    args = parser.parse_args()

    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    sections = build_report_sections(snapshot)
    cutoff_raw = snapshot.get("cutoff_at")
    cutoff = datetime.fromisoformat(cutoff_raw.replace("Z", "+00:00")) if cutoff_raw else None
    freshness = snapshot.get("freshness") or {}
    markdown, gate = render_markdown(sections, cutoff_at=cutoff, freshness=freshness)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    gate_path = Path(args.gate_out)
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(gate.to_dict(), ensure_ascii=False))
    return 0 if gate.status == "SELLABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
