from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromotionDecision:
    status: str
    reasons: tuple[str, ...]
    metrics: dict[str, Any]

    @property
    def promotable(self) -> bool:
        return self.status == "promotion_candidate"


def evaluate_regression_promotion(
    *,
    dataset_ready: bool,
    point_in_time_verified: bool,
    leakage_checks_passed: bool,
    out_of_sample_folds: int,
    mae_improvement: float,
    rmse_improvement: float,
    positive_fold_share: float,
    worst_fold_improvement: float,
    min_folds: int = 5,
    min_mae_improvement: float = 0.03,
    min_rmse_improvement: float = 0.03,
    min_positive_fold_share: float = 0.60,
    max_worst_fold_degradation: float = -0.20,
) -> PromotionDecision:
    reasons: list[str] = []
    if not dataset_ready:
        reasons.append("dataset_readiness_not_passed")
    if not point_in_time_verified:
        reasons.append("point_in_time_not_verified")
    if not leakage_checks_passed:
        reasons.append("leakage_checks_failed")
    if out_of_sample_folds < min_folds:
        reasons.append(f"out_of_sample_folds_below_{min_folds}")
    if mae_improvement < min_mae_improvement:
        reasons.append("mae_improvement_below_threshold")
    if rmse_improvement < min_rmse_improvement:
        reasons.append("rmse_improvement_below_threshold")
    if positive_fold_share < min_positive_fold_share:
        reasons.append("insufficient_fold_stability")
    if worst_fold_improvement < max_worst_fold_degradation:
        reasons.append("worst_fold_degradation_too_large")

    metrics = {
        "out_of_sample_folds": out_of_sample_folds,
        "mae_improvement": mae_improvement,
        "rmse_improvement": rmse_improvement,
        "positive_fold_share": positive_fold_share,
        "worst_fold_improvement": worst_fold_improvement,
    }
    if reasons:
        return PromotionDecision("research_only", tuple(reasons), metrics)
    return PromotionDecision("promotion_candidate", (), metrics)


def evaluate_probability_promotion(
    *,
    dataset_ready: bool,
    point_in_time_verified: bool,
    leakage_checks_passed: bool,
    out_of_sample_folds: int,
    brier_skill_score: float,
    positive_fold_share: float,
    worst_fold_improvement: float,
    calibration_error: float,
    min_folds: int = 5,
    min_brier_skill: float = 0.03,
    min_positive_fold_share: float = 0.60,
    max_worst_fold_degradation: float = -0.20,
    max_calibration_error: float = 0.10,
) -> PromotionDecision:
    reasons: list[str] = []
    if not dataset_ready:
        reasons.append("dataset_readiness_not_passed")
    if not point_in_time_verified:
        reasons.append("point_in_time_not_verified")
    if not leakage_checks_passed:
        reasons.append("leakage_checks_failed")
    if out_of_sample_folds < min_folds:
        reasons.append(f"out_of_sample_folds_below_{min_folds}")
    if brier_skill_score < min_brier_skill:
        reasons.append("brier_skill_below_threshold")
    if positive_fold_share < min_positive_fold_share:
        reasons.append("insufficient_fold_stability")
    if worst_fold_improvement < max_worst_fold_degradation:
        reasons.append("worst_fold_degradation_too_large")
    if calibration_error > max_calibration_error:
        reasons.append("calibration_error_above_threshold")

    metrics = {
        "out_of_sample_folds": out_of_sample_folds,
        "brier_skill_score": brier_skill_score,
        "positive_fold_share": positive_fold_share,
        "worst_fold_improvement": worst_fold_improvement,
        "calibration_error": calibration_error,
    }
    if reasons:
        return PromotionDecision("research_only", tuple(reasons), metrics)
    return PromotionDecision("promotion_candidate", (), metrics)
