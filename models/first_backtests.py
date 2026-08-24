from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

from .backtest import regression_metrics, rolling_origin_splits
from .baselines import deterministic_balance, moving_average, next_linear_trend, same_period_last_year, seasonal_mean


@dataclass(frozen=True)
class FoldPrediction:
    train_end: int
    test_index: int
    actual: float
    predictions: dict[str, float]

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class BacktestResult:
    model_id: str
    folds: tuple[FoldPrediction, ...]
    metrics: dict[str, dict[str, float | int | None]]
    status: str = "research_only_until_real_point_in_time_dataset"

    def to_dict(self):
        return asdict(self)


def _metrics(folds: Sequence[FoldPrediction]) -> dict[str, dict[str, float | int | None]]:
    names = sorted({name for fold in folds for name in fold.predictions})
    out: dict[str, dict[str, float | int | None]] = {}
    actual = [fold.actual for fold in folds]
    for name in names:
        predicted = [fold.predictions[name] for fold in folds]
        m = regression_metrics(actual, predicted)
        out[name] = {"n": m.n, "mae": m.mae, "rmse": m.rmse, "mape": m.mape}
    return out


def yield_backtest(values_by_season: Sequence[float], *, min_train: int = 5) -> BacktestResult:
    """Baseline-only rolling-origin harness for ALMT-SOY-YIELD-001.

    No weather features are inferred here. It establishes the hurdle the future model must beat.
    """
    values = [float(value) for value in values_by_season]
    folds: list[FoldPrediction] = []
    for train_idx, test_idx in rolling_origin_splits(len(values), min_train=min_train):
        train = [values[i] for i in train_idx]
        idx = test_idx.start
        predictions = {
            "moving_average_5_seasons": moving_average(train, min(5, len(train))),
            "linear_trend": next_linear_trend(train),
        }
        folds.append(FoldPrediction(train_idx.stop - 1, idx, values[idx], predictions))
    if not folds:
        raise ValueError("historico insuficiente para yield backtest")
    return BacktestResult("ALMT-SOY-YIELD-001", tuple(folds), _metrics(folds))


def balance_identity_backtest(rows: Sequence[dict[str, float]]) -> BacktestResult:
    """Checks official-vintage/accounting identity against realized ending stock rows."""
    folds: list[FoldPrediction] = []
    for idx, row in enumerate(rows):
        predicted = deterministic_balance(
            opening_stock=float(row["opening_stock"]), production=float(row["production"]),
            inflows=float(row.get("inflows", 0.0)), crush=float(row.get("crush", 0.0)),
            exports=float(row.get("exports", 0.0)), other_outflows=float(row.get("other_outflows", 0.0)),
        )
        folds.append(FoldPrediction(idx, idx, float(row["ending_stock"]), {"accounting_identity": predicted}))
    if not folds:
        raise ValueError("balance rows empty")
    return BacktestResult("ALMT-SOY-BALANCE-001", tuple(folds), _metrics(folds))


def export30_backtest(monthly_or_weekly_history: Sequence[float], *, seasonal_period: int = 12, min_years: int = 5) -> BacktestResult:
    """Seasonal baseline hurdle for ALMT-SOY-EXPORT30-001.

    The production model may later use line-up/commercialization/etc; this runner only establishes
    same-period-last-year and multi-year seasonal mean without future leakage.
    """
    values = [float(value) for value in monthly_or_weekly_history]
    min_train = seasonal_period * min_years
    folds: list[FoldPrediction] = []
    for train_idx, test_idx in rolling_origin_splits(len(values), min_train=min_train):
        train = [values[i] for i in train_idx]
        idx = test_idx.start
        predictions = {
            "same_period_last_year": same_period_last_year(train, seasonal_period),
            f"seasonal_mean_{min_years}_years": seasonal_mean(train, seasonal_period=seasonal_period, years=min_years),
        }
        folds.append(FoldPrediction(train_idx.stop - 1, idx, values[idx], predictions))
    if not folds:
        raise ValueError("historico insuficiente para export30 backtest")
    return BacktestResult("ALMT-SOY-EXPORT30-001", tuple(folds), _metrics(folds))
