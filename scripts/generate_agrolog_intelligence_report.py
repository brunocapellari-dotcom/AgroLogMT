#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from models.agrolog_intelligence_report import ReportSection, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AgroLog Intelligence commercial report from a structured snapshot.")
    parser.add_argument("--input", required=True, help="Structured JSON snapshot")
    parser.add_argument("--out", default="outputs/agrolog-intelligence-report.md")
    parser.add_argument("--gate-out", default="outputs/agrolog-intelligence-gate.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    sections = {}
    for item in payload.get("sections", []):
        section = ReportSection(
            title=item["title"],
            status=item.get("status", "SOURCE_GAP"),
            summary=item.get("summary", ""),
            bullets=tuple(item.get("bullets", [])),
            source_ids=tuple(item.get("source_ids", [])),
        )
        sections[section.title] = section

    cutoff_raw = payload.get("cutoff_at")
    cutoff = datetime.fromisoformat(cutoff_raw.replace("Z", "+00:00")) if cutoff_raw else None
    markdown, gate = render_markdown(sections, cutoff_at=cutoff, freshness=payload.get("freshness"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")

    gate_out = Path(args.gate_out)
    gate_out.parent.mkdir(parents=True, exist_ok=True)
    gate_out.write_text(json.dumps(gate.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(gate.to_dict(), ensure_ascii=False))
    return 0 if gate.status == "SELLABLE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
