#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from collector.imea_migration import render_validation_json, validate_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida pacote IMEA pré-produção antes de migração N6")
    parser.add_argument("root", help="Raiz do pacote IMEA que contém core/")
    parser.add_argument("--out", default="outputs/imea-migration-validation.json")
    parser.add_argument("--allow-partial", action="store_true", help="Não bloqueia somente pela ausência de grupos")
    args = parser.parse_args()

    result = validate_bundle(args.root, require_all=not args.allow_partial)
    text = render_validation_json(args.root, require_all=not args.allow_partial)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
