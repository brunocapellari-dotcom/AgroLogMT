from __future__ import annotations

import argparse
import json
from pathlib import Path

from .gaps import detect_gaps
from .models import SourceSpec
from .orchestrator import CollectorEngine
from .storage import LocalStore


def load_sources(path: str | Path) -> list[SourceSpec]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("sources", data)
    if not isinstance(rows, list):
        raise ValueError("Configuracao deve conter uma lista em 'sources'")
    return [SourceSpec.from_dict(row) for row in rows]


def cmd_run(args: argparse.Namespace) -> int:
    specs = load_sources(args.config)
    selected = [s for s in specs if (not args.source or s.source_id == args.source) and (not args.group or s.group == args.group)]
    if not selected:
        raise SystemExit("Nenhuma fonte selecionada")
    engine = CollectorEngine(store=LocalStore(args.root))
    exit_code = 0
    for spec in selected:
        manifest = engine.run_source(spec)
        print(json.dumps(manifest.to_dict(), ensure_ascii=False))
        if manifest.status == "error":
            exit_code = 1
    return exit_code


def cmd_gaps(args: argparse.Namespace) -> int:
    observed = json.loads(Path(args.observed).read_text(encoding="utf-8"))
    if isinstance(observed, dict):
        observed = observed.get("observed", [])
    missing = detect_gaps(observed, args.start, args.end, args.frequency)
    print(json.dumps({"missing": missing, "count": len(missing)}, ensure_ascii=False))
    return 2 if missing else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgroLog MT - motor generico de coleta")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Executa uma ou mais fontes")
    run.add_argument("--config", required=True)
    run.add_argument("--root", default=None, help="Raiz RAW/state/manifests; AGROLOG_RAW_ROOT e o default")
    run.add_argument("--source")
    run.add_argument("--group", choices=["radar", "dados", "conhecimento"])
    run.set_defaults(func=cmd_run)

    gaps = sub.add_parser("audit-gaps", help="Detecta referencias ausentes")
    gaps.add_argument("--observed", required=True, help="JSON lista ou {'observed': [...]}")
    gaps.add_argument("--start", required=True, help="YYYY-MM-DD")
    gaps.add_argument("--end", required=True, help="YYYY-MM-DD")
    gaps.add_argument("--frequency", required=True, choices=["daily", "business_daily", "weekly", "monthly"])
    gaps.set_defaults(func=cmd_gaps)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
