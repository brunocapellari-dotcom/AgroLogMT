#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from models.backtest import regression_metrics

TABLE_ID = 1612
MT_UF_CODE = 51
YIELD_VARIABLE = 112
SOY_CATEGORY = 2713
PRIMARY_URL = (
    "https://apisidra.ibge.gov.br/values/t/1612/n3/51/v/112/p/all/c81/2713?formato=json"
)
FALLBACK_URL = (
    "https://api.sidra.ibge.gov.br/values/t/1612/n3/51/v/112/p/all/c81/2713?formato=json"
)


@dataclass(frozen=True)
class YieldObservation:
    year: int
    yield_kg_ha: float
    geo: str
    variable: str
    product: str


@dataclass(frozen=True)
class LaggedFold:
    target_year: int
    last_available_year: int
    actual: float
    moving_average_5: float
    linear_trend_horizon: float


def _fetch_json(url: str, *, timeout: int = 90) -> tuple[list[dict], str]:
    request = Request(url, headers={"User-Agent": "AgroLogMT/0.1 (+ibge-pam-yield-hurdle)"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise ValueError("SIDRA: resposta nao e lista")
        return payload, response.geturl()


def fetch_sidra() -> tuple[list[dict], str]:
    errors: list[str] = []
    for url in (PRIMARY_URL, FALLBACK_URL):
        try:
            return _fetch_json(url)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    raise RuntimeError("SIDRA indisponivel: " + " | ".join(errors))


def _number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"-", "...", "..", "X"}:
        return None
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        value_float = float(text)
    except ValueError:
        return None
    return value_float if math.isfinite(value_float) else None


def parse_sidra_rows(payload: list[dict]) -> list[YieldObservation]:
    if len(payload) < 2:
        raise ValueError("SIDRA: resposta sem linhas de dados")
    rows: list[YieldObservation] = []
    for row in payload[1:]:
        geo = str(row.get("D1N") or "").strip()
        variable = str(row.get("D2N") or "").strip()
        period = str(row.get("D3N") or row.get("D3C") or "").strip()
        product = str(row.get("D4N") or "").strip()
        value = _number(row.get("V"))
        if geo != "Mato Grosso":
            continue
        if "Rendimento" not in variable:
            continue
        if "Soja" not in product:
            continue
        if value is None:
            continue
        try:
            year = int(period)
        except ValueError:
            continue
        rows.append(YieldObservation(year, value, geo, variable, product))
    rows.sort(key=lambda item: item.year)
    if not rows:
        sample = payload[1] if len(payload) > 1 else {}
        raise ValueError(f"SIDRA: nenhuma linha soja/rendimento/MT; amostra={sample}")
    if len({item.year for item in rows}) != len(rows):
        raise ValueError("SIDRA: anos duplicados para soja MT rendimento")
    return rows


def linear_trend_at_horizon(values: list[float], horizon: int) -> float:
    if len(values) < 2:
        return values[-1]
    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = mean(values)
    denom = sum((x - x_mean) ** 2 for x in range(n))
    if denom <= 0:
        return y_mean
    slope = sum((x - x_mean) * (values[x] - y_mean) for x in range(n)) / denom
    intercept = y_mean - slope * x_mean
    target_x = (n - 1) + horizon
    return intercept + slope * target_x


def lagged_hurdle(
    observations: list[YieldObservation], *, label_lag_years: int = 2, min_train: int = 5
) -> dict:
    values = [item.yield_kg_ha for item in observations]
    years = [item.year for item in observations]
    folds: list[LaggedFold] = []
    for target_idx in range(len(values)):
        last_available_idx = target_idx - label_lag_years
        if last_available_idx < 0:
            continue
        train = values[: last_available_idx + 1]
        if len(train) < min_train:
            continue
        folds.append(
            LaggedFold(
                target_year=years[target_idx],
                last_available_year=years[last_available_idx],
                actual=values[target_idx],
                moving_average_5=mean(train[-5:]),
                linear_trend_horizon=linear_trend_at_horizon(train, label_lag_years),
            )
        )
    if not folds:
        raise ValueError("PAM: historico insuficiente para hurdle com lag conservador")
    actual = [fold.actual for fold in folds]
    ma = [fold.moving_average_5 for fold in folds]
    trend = [fold.linear_trend_horizon for fold in folds]
    ma_metrics = regression_metrics(actual, ma)
    trend_metrics = regression_metrics(actual, trend)
    return {
        "model_id": "ALMT-SOY-YIELD-001",
        "status": "research_only",
        "forecast_context": "pre_season_conservative_label_availability",
        "label_lag_years": label_lag_years,
        "min_train": min_train,
        "folds": [asdict(fold) for fold in folds],
        "metrics": {
            "moving_average_5": asdict(ma_metrics),
            "linear_trend_horizon": asdict(trend_metrics),
        },
    }


def build_snapshot(*, label_lag_years: int = 2, min_train: int = 5) -> dict:
    payload, observed_url = fetch_sidra()
    observations = parse_sidra_rows(payload)
    hurdle = lagged_hurdle(observations, label_lag_years=label_lag_years, min_train=min_train)
    latest = observations[-1]
    return {
        "dataset": "IBGE PAM Soja MT realized annual yield target",
        "table_id": TABLE_ID,
        "source_id": "ibge_sidra_pam_1612",
        "source_url": observed_url,
        "geo_code": MT_UF_CODE,
        "variable_code": YIELD_VARIABLE,
        "category_code": SOY_CATEGORY,
        "evidence_class": "observado",
        "target_role": "realized_label_not_point_in_time_feature",
        "series_start": observations[0].year,
        "series_end": latest.year,
        "n_years": len(observations),
        "latest_yield_kg_ha": latest.yield_kg_ha,
        "observations": [asdict(item) for item in observations],
        "hurdle": hurdle,
        "limitations": [
            "PAM e uma serie anual final/revisavel e deve ser usada como target realizado, nao como feature contemporanea antes de sua publicacao.",
            "O hurdle usa lag conservador de labels para evitar assumir disponibilidade imediata da PAM do ano anterior.",
            "Baselines de media movel e tendencia nao incorporam clima, tecnologia, area, solo ou manejo e permanecem research_only.",
            "Promocao N6 exige features point-in-time, mais benchmarks, estabilidade, validacao por regimes e auditoria independente.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Hurdle historico de produtividade de soja MT com PAM/IBGE")
    parser.add_argument("--label-lag-years", type=int, default=2)
    parser.add_argument("--min-train", type=int, default=5)
    parser.add_argument("--out", default="ibge_pam_soy_yield_hurdle.json")
    args = parser.parse_args()
    snapshot = build_snapshot(label_lag_years=args.label_lag_years, min_train=args.min_train)
    Path(args.out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "series_start": snapshot["series_start"],
        "series_end": snapshot["series_end"],
        "n_years": snapshot["n_years"],
        "folds": len(snapshot["hurdle"]["folds"]),
        "metrics": snapshot["hurdle"]["metrics"],
        "status": snapshot["hurdle"]["status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
