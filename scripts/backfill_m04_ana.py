from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from collector.cloud_store import DriveBigQueryStore
from collector.models import SourceSpec
from collector.p0_pipeline import run_ana_hydro_pipeline

DEFAULT_STATIONS = ["15400000", "15320002", "15630000", "17730000", "17900000"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill ANA HidroWeb M04 em janelas de até 30 dias.")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--stations", default=",".join(DEFAULT_STATIONS))
    parser.add_argument("--range", default="DIAS_30")
    return parser.parse_args()


def window_end_dates(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("end anterior a start")
    cursor = min(start + timedelta(days=29), end)
    out: list[date] = []
    while True:
        out.append(cursor)
        if cursor >= end:
            break
        cursor = min(cursor + timedelta(days=30), end)
    return out


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    stations = [item.strip() for item in args.stations.split(",") if item.strip()]
    if not stations:
        raise SystemExit("Nenhuma estação informada")

    store = DriveBigQueryStore()
    runs = []
    failed = 0
    for search_date in window_end_dates(start, end):
        spec = SourceSpec(
            source_id="ana_hidroweb_m04_stations",
            name="ANA HidroWebService - backfill M04",
            group="dados",
            method="ana_hidroweb_adopted",
            enabled=True,
            expected_frequency="backfill",
            file_extension="json",
            evidence_class="observado",
            options={
                "station_codes": stations,
                "date_filter": "DATA_LEITURA",
                "range_filter": args.range,
                "search_date": search_date.isoformat(),
                "identificador_env_var": "ANA_IDENTIFICADOR",
                "senha_env_var": "ANA_SENHA",
                "timeout_seconds": 120,
            },
            notes="Backfill M04; RAW e curated preservados; credenciais somente por ambiente/Secret Manager.",
        )
        code, payload = run_ana_hydro_pipeline(spec, store)
        runs.append({"search_date": search_date.isoformat(), "code": code, "result": payload})
        print(json.dumps(runs[-1], ensure_ascii=False, sort_keys=True), flush=True)
        if code:
            failed += 1
            # Fail closed: não avança silenciosamente após um chunk quebrado.
            break

    summary = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "stations": stations,
        "windows_attempted": len(runs),
        "failed_windows": failed,
        "status": "PASS" if not failed else "PARTIAL_BLOCKED",
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
