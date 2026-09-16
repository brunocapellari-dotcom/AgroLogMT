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


def query_year(year: int, *, timeout: int = 120, retries: int = 6) -> dict[str, Any]:
    body = {
        "flow": "export",
        "monthDetail": False,
        "period": {"from": f"{year}-01", "to": f"{year}-12"},
        "filters": [],
        "details": ["ncm"],
        "metrics": ["metricKG"],
    }
    last_error: Exception | None = None
    with requests.Session() as session:
        session.headers.update({"User-Agent": "AgroLogMT/0.1 (+beef-ncm-history)"})
        for attempt in range(retries):
            try:
                response = session.post(API_URL, json=body, timeout=timeout)
                if response.status_code in {429, 500, 502, 503, 504}:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else min(90.0, 15.0 * (attempt + 1))
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                payload = response.json()
                if payload.get("success") is False:
                    raise RuntimeError(f"Comex Stat API reported failure for {year}: {payload.get('message')}")
                rows = _rows(payload)
                codes: set[str] = set()
                for row in rows:
                    codes.update(_find_beef_codes(row))
                if not codes:
                    raise RuntimeError(f"No observed 0201/0202 NCM code for {year}")
                return {
                    "year": year,
                    "beef_ncm_codes": sorted(codes),
                    "result_rows": len(rows),
                }
            except Exception as exc:
                last_error = exc
                if attempt + 1 < retries:
                    time.sleep(min(90.0, 15.0 * (attempt + 1)))
    raise RuntimeError(f"Comex Stat year {year} unavailable after {retries} attempts: {last_error}")


def probe_history(start_year: int, end_year: int, *, inter_year_delay: float = 15.0) -> dict[str, Any]:
    if start_year < 1997 or end_year < start_year:
        raise ValueError("invalid Comex Stat year range")
    years: list[dict[str, Any]] = []
    union_codes: set[str] = set()
    for index, year in enumerate(range(start_year, end_year + 1)):
        result = query_year(year)
        years.append(result)
        union_codes.update(result["beef_ncm_codes"])
        if index + 1 < end_year - start_year + 1:
            time.sleep(max(0.0, inter_year_delay))
    return {
        "start_year": start_year,
        "end_year": end_year,
        "years": years,
        "observed_union_ncm_codes": sorted(union_codes),
        "years_validated": len(years),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe observed 0201/0202 NCM codes in official Comex Stat exports year by year.")
    parser.add_argument("--from-year", type=int, default=1997)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument("--inter-year-delay", type=float, default=15.0)
    parser.add_argument("--out", default="comex_beef_ncm_history_probe.json")
    args = parser.parse_args()

    failed = False
    try:
        result = probe_history(args.from_year, args.to_year, inter_year_delay=args.inter_year_delay)
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
        "method": "annual_observed_ncm_export_codes",
        "period": result,
    }
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
