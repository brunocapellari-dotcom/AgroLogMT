from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RegressionMetrics:
    n: int
    mae: float
    rmse: float
    mape: float | None


def regression_metrics(actual: Sequence[float], predicted: Sequence[float]) -> RegressionMetrics:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual e predicted devem ter mesmo tamanho nao vazio")
    errors = [p - a for a, p in zip(actual, predicted)]
    mae = sum(abs(err) for err in errors) / len(errors)
    rmse = math.sqrt(sum(err * err for err in errors) / len(errors))
    pct = [abs((p - a) / a) for a, p in zip(actual, predicted) if a != 0]
    mape = (sum(pct) / len(pct)) if pct else None
    return RegressionMetrics(n=len(errors), mae=mae, rmse=rmse, mape=mape)


def brier_score(outcomes: Sequence[int], probabilities: Sequence[float]) -> float:
    if len(outcomes) != len(probabilities) or not outcomes:
        raise ValueError("outcomes e probabilities devem ter mesmo tamanho nao vazio")
    if any(outcome not in {0, 1} for outcome in outcomes):
        raise ValueError("outcomes devem ser binarios")
    if any(prob < 0 or prob > 1 for prob in probabilities):
        raise ValueError("probabilidades devem estar em [0,1]")
    return sum((prob - outcome) ** 2 for outcome, prob in zip(outcomes, probabilities)) / len(outcomes)


def directional_accuracy(actual_changes: Sequence[float], predicted_changes: Sequence[float]) -> float:
    if len(actual_changes) != len(predicted_changes) or not actual_changes:
        raise ValueError("series devem ter mesmo tamanho nao vazio")
    hits = sum((a >= 0) == (p >= 0) for a, p in zip(actual_changes, predicted_changes))
    return hits / len(actual_changes)


def rolling_origin_splits(n: int, *, min_train: int, horizon: int = 1, step: int = 1) -> list[tuple[range, range]]:
    if n <= 0 or min_train <= 0 or horizon <= 0 or step <= 0:
        raise ValueError("parametros devem ser positivos")
    if min_train + horizon > n:
        return []
    splits: list[tuple[range, range]] = []
    origin = min_train
    while origin + horizon <= n:
        splits.append((range(0, origin), range(origin, origin + horizon)))
        origin += step
    return splits
