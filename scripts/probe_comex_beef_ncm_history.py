from __future__ import annotations

import argparse
import json
import re
import time
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


def _post(body: dict[str, Any], *, timeout: int = 120, retries: int = 4) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.post(API_URL, json=body, timeout=timeout)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 5.0 * (attempt + 1)
                time.sleep(delay)
                continue
            response.raise_for_status()
            payload = response.json()
            if payload.get("success") is False:
                raise RuntimeError(f"Comex Stat API reported failure: {payload.get('message')}")
            return payload
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(3.0 * (attempt + 1))
    raise RuntimeError(f"Comex Stat API unavailable after {retries} attempts: {last_error}")


def query_period(start_year: int, end_year: int, *, timeout: int = 120) -> dict[str, Any]:
    if start_year > end_year:
        raise ValueError("start_year posterior a end_year")
    body = {
        "flow": "export",
        "monthDetail": False,
        "period": {"from": f"{start_year}-01", "to": f"{end_year}-12"},
        "filters": [],
        "details": ["ncm"],
        "metrics": ["metricKG"],
    }
    payload = _post(body, timeout=timeout)
    rows = _rows(payload)
    codes: set[str] = set()
    for row in rows:
        codes.update(_find_beef_codes(row))
    if not codes:
        sample = rows[:3]
        raise RuntimeError(f"No 0201/0202 NCM code found for {start_year}-{end_year}; sample={sample!r}")
    return {
        "start_year": start_year,
        "end_year": end_year,
        "beef_ncm_codes": sorted(codes),
        "result_rows": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe 0201/0202 NCM codes used by official Comex Stat exports.")
    parser.add_argument("--from-year", type=int, default=1997)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument("--out", default="comex_beef_ncm_history_probe.json")
    args = parser.parse_args()
    if args.from_year < 1997 or args.to_year > 2100:
        raise ValueError("years outside Comex Stat NCM scope")

    failed = False
    try:
        result = query_period(args.from_year, args.to_year)
    except Exception as exc:
        failed = True
        result = {
            "start_year": args.from_year,
            "end_year": args.to_year,
            "error": f"{type(exc).__name__}: {exc}",
        }

    payload = {
        "status": "error" if failed else "ok",
        "source": API_URL,
        "period": result,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
