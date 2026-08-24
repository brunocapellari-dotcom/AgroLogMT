#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.adapters import get_adapter
from collector.cli import load_sources
from collector.conab_safra import parse_conab_safra_workbook, select_current
from collector.xlsx_reader import read_xlsx


def _compact_row(row):
    out = []
    for value in row[:30]:
        if isinstance(value, str):
            value = value.strip()
            if len(value) > 120:
                value = value[:117] + "..."
        out.append(value)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe read-only do XLSX oficial mais recente da CONAB Safra")
    ap.add_argument("--config", default="collector/config/sources.pilot.json")
    ap.add_argument("--source-id", default="conab_safra_graos_xlsx")
    ap.add_argument("--out", default="conab_safra_probe.json")
    args = ap.parse_args()

    specs = {spec.source_id: spec for spec in load_sources(Path(args.config))}
    spec = specs.get(args.source_id)
    if spec is None:
        raise SystemExit(f"Fonte não encontrada: {args.source_id}")

    result = get_adapter(spec.method).fetch(spec)
    sheets = read_xlsx(result.payload)
    records = parse_conab_safra_workbook(result.payload)
    targets = {}
    for geo_id, product_id in (("MT", "soja"), ("MT", "milho_2_safra"), ("MT", "algodao_pluma"), ("BR", "soja")):
        record = select_current(records, geo_id=geo_id, product_id=product_id)
        targets[f"{geo_id}:{product_id}"] = record.to_dict()

    current = [record for record in records if record.vintage_position == "current"]
    flagged = [record for record in current if record.quality_flags]
    report = {
        "source_id": spec.source_id,
        "observed_url": result.observed_url,
        "content_type": result.content_type,
        "bytes": len(result.payload),
        "parsed": {
            "records": len(records),
            "current_records": len(current),
            "geo_ids": sorted({record.geo_id for record in records}),
            "products": len({record.product_id for record in current}),
            "current_quality_flagged": len(flagged),
            "quality_flag_examples": [record.to_dict() for record in flagged[:25]],
            "targets": targets,
        },
        "sheets": [],
    }
    for sheet in sheets:
        nonempty = [row for row in sheet.rows if any(v not in (None, "") for v in row)]
        report["sheets"].append({
            "name": sheet.name,
            "rows": len(sheet.rows),
            "nonempty_rows": len(nonempty),
            "max_columns": max((len(r) for r in sheet.rows), default=0),
            "sample": [_compact_row(row) for row in nonempty[:20]],
        })

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
