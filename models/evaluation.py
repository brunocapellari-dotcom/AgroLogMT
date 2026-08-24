from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .backtest import brier_score, regression_metrics


@dataclass(frozen=True)
class RegressionSkill:
    model_mae: float
    baseline_mae: float
    mae_improvement: float
    model_rmse: float
    baseline_rmse: float
    rmse_improvement: float


@dataclass(frozen=True)
class ProbabilitySkill:
    model_brier: float
    baseline_brier: float
    brier_skill_score: float


@dataclass(frozen=True)
class StabilityResult:
    folds: int
    positive_folds: int
    positive_share: float
    worst_improvement: float
    median_improvement: float


def _relative_improvement(model_loss: float, baseline_loss: float) -> float:
    if baseline_loss < 0 or model_loss < 0:
        raise ValueError("losses nao podem ser negativos")
    if baseline_loss == 0:
        return 0.0 if model_loss == 0 else float("-inf")
    return (baseline_loss - model_loss) / baseline_loss


def regression_skill(
    actual: Sequence[float],
    model_predictions: Sequence[float],
    baseline_predictions: Sequence[float],
) -> RegressionSkill:
    model = regression_metrics(actual, model_predictions)
    baseline = regression_metrics(actual, baseline_predictions)
    return RegressionSkill(
        model_mae=model.mae,
        baseline_mae=baseline.mae,
        mae_improvement=_relative_improvement(model.mae, baseline.mae),
        model_rmse=model.rmse,
        baseline_rmse=baseline.rmse,
        rmse_improvement=_relative_improvement(model.rmse, baseline.rmse),
    )


def probability_skill(
    outcomes: Sequence[int],
    model_probabilities: Sequence[float],
    baseline_probabilities: Sequence[float],
) -> ProbabilitySkill:
    model = brier_score(outcomes, model_probabilities)
    baseline = brier_score(outcomes, baseline_probabilities)
    return ProbabilitySkill(
        model_brier=model,
        baseline_brier=baseline,
        brier_skill_score=_relative_improvement(model, baseline),
    )


def stability(improvements: Sequence[float]) -> StabilityResult:
    if not improvements:
        raise ValueError("improvements vazio")
    ordered = sorted(float(value) for value in improvements)
    n = len(ordered)
    if n % 2:
        median = ordered[n // 2]
    else:
        median = (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    positive = sum(value > 0 for value in ordered)
    return StabilityResult(
        folds=n,
        positive_folds=positive,
        positive_share=positive / n,
        worst_improvement=ordered[0],
        median_improvement=median,
    )
