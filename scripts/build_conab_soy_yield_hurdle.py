#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

from collector.conab_safra import parse_conab_safra_workbook
from collector.conab_safra_history import discover_archive_by_pattern, discover_publications
from models.first_backtests import yield_backtest
from scripts.backfill_conab_safra import merge_publications


def _download(url: str, timeout: int = 120) -> bytes:
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+conab-yield-hurdle)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _season_start(safra: str) -> int:
    text = safra.strip()
    if "/" not in text:
        raise ValueError(f"safra invalida: {safra}")
    head = text.split("/", 1)[0]
    if len(head) == 2:
        return 2000 + int(head)
    return int(head)


def build_annual_series(*, start_year: int = 2021, end_year: int = 2025) -> dict:
    listing = discover_publications()
    archive = discover_archive_by_pattern(start_year=start_year, end_year=end_year)
    publications = merge_publications(listing, archive)
    by_safra = defaultdict(list)
    for publication in publications:
        if publication.safra and publication.levantamento and publication.data_publicacao:
            by_safra[publication.safra].append(publication)

    chosen = []
    for safra, items in by_safra.items():
        best = max(items, key=lambda item: (item.levantamento or 0, item.data_publicacao or ""))
        chosen.append(best)
    chosen.sort(key=lambda item: _season_start(item.safra or "0/0"))

    seasons: dict[str, dict] = {}
    source_vintages = []
    for publication in chosen:
        payload = _download(publication.attachment_url)
        rows = parse_conab_safra_workbook(payload)
        soy = [row for row in rows if row.geo_id == "MT" and row.product_id == "soja"]
        current = next((row for row in soy if row.vintage_position == "current"), None)
        previous = next((row for row in soy if row.vintage_position == "previous"), None)
        if current is None:
            continue
        source_vintages.append({
            "source_safra": publication.safra,
            "levantamento": publication.levantamento,
            "data_publicacao": publication.data_publicacao,
            "availability_basis": publication.availability_basis,
            "current_safra": current.safra,
            "current_yield_kg_ha": current.produtividade_kg_ha,
            "previous_safra": previous.safra if previous else None,
            "previous_yield_kg_ha": previous.produtividade_kg_ha if previous else None,
        })
        # Prefer a row where the season is the current vintage. Previous rows only fill gaps.
        seasons[current.safra] = {
            "safra": current.safra,
            "produtividade_kg_ha": float(current.produtividade_kg_ha),
            "source_safra": publication.safra,
            "source_levantamento": publication.levantamento,
            "data_publicacao": publication.data_publicacao,
            "vintage_position": "current",
            "is_latest_available_vintage": True,
        }
        if previous is not None and previous.safra not in seasons:
            seasons[previous.safra] = {
                "safra": previous.safra,
                "produtividade_kg_ha": float(previous.produtividade_kg_ha),
                "source_safra": publication.safra,
                "source_levantamento": publication.levantamento,
                "data_publicacao": publication.data_publicacao,
                "vintage_position": "previous",
                "is_latest_available_vintage": False,
            }

    ordered = sorted(seasons.values(), key=lambda item: _season_start(item["safra"]))
    values = [item["produtividade_kg_ha"] for item in ordered]
    result = {
        "dataset": "CONAB Soja MT annual yield hurdle",
        "status": "research_only",
        "series": ordered,
        "source_vintages": source_vintages,
        "n_seasons": len(ordered),
        "season_start": ordered[0]["safra"] if ordered else None,
        "season_end": ordered[-1]["safra"] if ordered else None,
        "warnings": [],
    }
    if len(values) >= 6:
        backtest = yield_backtest(values, min_train=5).to_dict()
        result["backtest"] = backtest
        result["folds"] = len(backtest["folds"])
        if len(backtest["folds"]) < 5:
            result["warnings"].append("Poucos folds rolling-origin; resultado serve apenas como hurdle preliminar e nao autoriza promocao.")
    else:
        result["backtest"] = None
        result["folds"] = 0
        result["warnings"].append("Historico insuficiente para o hurdle YIELD com treino minimo de 5 safras.")
    if ordered and ordered[-1]["source_levantamento"] < 12:
        result["warnings"].append("A safra mais recente ainda nao possui 12o levantamento no inventario; nao tratar como realizado final.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Constroi hurdle anual de produtividade de soja MT a partir de vintages CONAB")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--out", default="conab_soy_yield_hurdle.json")
    args = parser.parse_args()
    result = build_annual_series(start_year=args.start_year, end_year=args.end_year)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "n_seasons": result["n_seasons"],
        "folds": result["folds"],
        "season_start": result["season_start"],
        "season_end": result["season_end"],
        "warnings": result["warnings"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["n_seasons"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
