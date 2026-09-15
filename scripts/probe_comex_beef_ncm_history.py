from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import requests

API_URL = "https://api-comexstat.mdic.gov.br/general?language=pt"
BEEF_NCM_PATTERN = re.compile(r"^020[12][0-9]{4}$")


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, dict):
        rows = data.get("list")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    raise ValueError("Comex Stat API response without data.list")


def _find_beef_codes(row: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)
        elif isinstance(value, (str, int)):
            text = str(value).strip()
            if BEEF_NCM_PATTERN.fullmatch(text):
                found.add(text)

    walk(row)
    return found


def query_year(year: int, *, timeout: int = 120) -> dict[str, Any]:
    body = {
        "flow": "export",
        "monthDetail": False,
        "period": {"from": f"{year}-01", "to": f"{year}-12"},
        "filters": [],
        "details": ["ncm"],
        "metrics": ["metricKG"],
    }
    response = requests.post(API_URL, json=body, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if payload.get("success") is False:
        raise RuntimeError(f"Comex Stat API reported failure for {year}: {payload.get('message')}")
    rows = _rows(payload)
    codes: set[str] = set()
    for row in rows:
        codes.update(_find_beef_codes(row))
    if not codes:
        raise RuntimeError(f"No 0201/0202 NCM code found for {year}")
    return {
        "year": year,
        "beef_ncm_codes": sorted(codes),
        "result_rows": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe historical 0201/0202 NCM codes used by official Comex Stat exports.")
    parser.add_argument("--year", type=int, action="append", dest="years")
    parser.add_argument("--out", default="comex_beef_ncm_history_probe.json")
    args = parser.parse_args()
    years = args.years or [1997, 2001, 2002, 2003, 2004]
    if any(year < 1997 or year > 2100 for year in years):
        raise ValueError("years outside Comex Stat NCM scope")

    results = [query_year(year) for year in years]
    payload = {
        "status": "ok",
        "source": API_URL,
        "years": results,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
