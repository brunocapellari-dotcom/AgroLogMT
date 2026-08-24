#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from collector.conab_safra_history import discover_publications


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventário read-only das publicações históricas CONAB Safra visíveis na listagem oficial")
    ap.add_argument("--out", default="conab_safra_history_probe.json")
    args = ap.parse_args()
    publications = discover_publications()
    report = {
        "count": len(publications),
        "safras": sorted({p.safra for p in publications if p.safra}, reverse=True),
        "publications": [p.to_dict() for p in publications],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
