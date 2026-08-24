#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from collector.imea_operational_xlsx import parse_workbook


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida imea-1.xlsx sem qualquer escrita externa")
    ap.add_argument("file")
    ap.add_argument("--out", default="imea_operational_validation.json")
    args = ap.parse_args()
    payload = Path(args.file).read_bytes()
    parsed = parse_workbook(payload)
    report = {
        "file": str(args.file),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "qa": parsed["qa"],
        "status": "pass",
        "note": "frete permanece indicador de referencia IMEA; negotiated=false",
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
