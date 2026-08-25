#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from collector.comexstat_api import ComexStatApiClient, soybean_export_payload
from models.first_backtests import export30_backtest


def month_range(start_year: int, start_month: int, end_year: int, end_month: int) -> list[str]:
    if (start_year, start_month) > (end_year, end_month):
        raise ValueError("inicio deve ser <= fim")
    out: list[str] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        out.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return out


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("list", "data"):
            rows = data.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise RuntimeError("ComexStat API sem lista de resultados reconhecivel")


def _fetch_full_month_block(
    client: ComexStatApiClient,
    *,
    start_year: int,
    end_year: int,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Solicita meses 01-12 para todos os anos em uma única chamada.

    A semântica da API aplica o intervalo de meses a cada ano. Portanto 01-12
    recupera todos os meses de cada ano; meses futuros do ano corrente não geram
    grupos e são removidos depois usando a competência oficial de atualização.
    """
    start = f"{start_year:04d}-01"
    end = f"{end_year:04d}-12"
    result = client.general(soybean_export_payload(start=start, end=end, month_detail=True))
    rows = _rows(result)
    return rows, [{"from": start, "to": end, "rows": str(len(rows))}]


def build_history(*, start_year: int = 2015, state: str = "Mato Grosso", client: ComexStatApiClient | None = None) -> dict[str, Any]:
    client = client or ComexStatApiClient(timeout=180)
    update = client.last_update()
    if update.year is None or update.month is None:
        raise RuntimeError("ComexStat API sem competencia atual")
    if start_year < 1997 or start_year > update.year:
        raise ValueError("start_year fora da cobertura moderna")

    rows, request_periods = _fetch_full_month_block(
        client, start_year=start_year, end_year=update.year
    )

    monthly: dict[str, dict[str, float]] = {}
    for row in rows:
        if str(row.get("state") or "").strip().casefold() != state.casefold():
            continue
        year = int(row["year"])
        month = int(row["monthNumber"])
        if (year, month) > (update.year, update.month):
            continue
        period = f"{year:04d}-{month:02d}"
        kg = float(row.get("metricKG") or 0.0)
        fob = float(row.get("metricFOB") or 0.0)
        bucket = monthly.setdefault(period, {"kg": 0.0, "fob_usd": 0.0})
        bucket["kg"] += kg
        bucket["fob_usd"] += fob

    periods = month_range(start_year, 1, update.year, update.month)
    series: list[dict[str, Any]] = []
    missing_groups: list[str] = []
    for period in periods:
        values = monthly.get(period)
        if values is None:
            missing_groups.append(period)
            values = {"kg": 0.0, "fob_usd": 0.0}
        tonnes = values["kg"] / 1000.0
        series.append({
            "period": period,
            "tonnes": tonnes,
            "kg": values["kg"],
            "fob_usd": values["fob_usd"],
            "usd_per_t": values["fob_usd"] / tonnes if tonnes > 0 else None,
        })

    values = [row["tonnes"] for row in series]
    backtest = export30_backtest(values, seasonal_period=12, min_years=5).to_dict()
    zero_actual_folds = sum(1 for fold in backtest["folds"] if float(fold["actual"]) == 0.0)
    return {
        "dataset": "ComexStat API soybean exports Mato Grosso",
        "source_id": "mdic_comexstat_api",
        "state": state,
        "ncm": ["12011000", "12019000"],
        "period_start": periods[0],
        "period_end": periods[-1],
        "n_months": len(series),
        "api_updated": update.updated,
        "request_periods": request_periods,
        "series": series,
        "missing_group_months_assumed_zero": missing_groups,
        "backtest": backtest,
        "metric_quality": {
            "zero_actual_folds": zero_actual_folds,
            "mape_usable": zero_actual_folds == 0,
            "primary_metrics": ["mae", "rmse"] if zero_actual_folds else ["mae", "rmse", "mape"],
        },
        "status": "research_only",
        "warnings": [
            "Ausencia de grupo mensal na resposta agregada da API e tratada como zero; validar contra microdados antes de promocao.",
            "MAPE nao deve ser interpretado quando houver actual=0 em folds; MAE/RMSE permanecem os hurdles primarios nesses casos.",
            "SG_UF_NCM/state representa UF do produto na semantica ComexStat; nao confundir com municipio de origem fisica ou porto.",
            "O hurdle mensal testa sazonalidade historica; EXPORT30 produtivo ainda deve incorporar informacao point-in-time adicional e validar release ledger.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Hurdle EXPORT30 de soja MT via API ComexStat")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--state", default="Mato Grosso")
    parser.add_argument("--out", default="comex_soy_export30_hurdle.json")
    args = parser.parse_args()
    result = build_history(start_year=args.start_year, state=args.state)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "period_start": result["period_start"],
        "period_end": result["period_end"],
        "n_months": result["n_months"],
        "zero_group_months": len(result["missing_group_months_assumed_zero"]),
        "metric_quality": result["metric_quality"],
        "metrics": result["backtest"]["metrics"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
