from __future__ import annotations

import unittest

from models.evaluation import probability_skill, regression_skill, stability
from models.promotion import evaluate_probability_promotion, evaluate_regression_promotion


class EvaluationTests(unittest.TestCase):
    def test_regression_skill_rewards_lower_error_than_baseline(self) -> None:
        actual = [100, 110, 120, 130]
        model = [101, 109, 121, 129]
        baseline = [95, 105, 115, 125]
        skill = regression_skill(actual, model, baseline)
        self.assertGreater(skill.mae_improvement, 0)
        self.assertGreater(skill.rmse_improvement, 0)

    def test_probability_skill_uses_brier_against_baseline(self) -> None:
        outcomes = [0, 1, 1, 0]
        model = [0.1, 0.8, 0.9, 0.2]
        baseline = [0.5, 0.5, 0.5, 0.5]
        skill = probability_skill(outcomes, model, baseline)
        self.assertGreater(skill.brier_skill_score, 0)

    def test_stability_reports_worst_fold(self) -> None:
        result = stability([0.10, 0.05, -0.02, 0.08, 0.04])
        self.assertEqual(result.folds, 5)
        self.assertEqual(result.positive_folds, 4)
        self.assertAlmostEqual(result.positive_share, 0.8)
        self.assertEqual(result.worst_improvement, -0.02)


class PromotionTests(unittest.TestCase):
    def test_regression_candidate_requires_data_oos_and_stability(self) -> None:
        decision = evaluate_regression_promotion(
            dataset_ready=True,
            point_in_time_verified=True,
            leakage_checks_passed=True,
            out_of_sample_folds=8,
            mae_improvement=0.08,
            rmse_improvement=0.06,
            positive_fold_share=0.75,
            worst_fold_improvement=-0.10,
        )
        self.assertTrue(decision.promotable)

    def test_regression_model_is_research_only_when_average_gain_is_unstable(self) -> None:
        decision = evaluate_regression_promotion(
            dataset_ready=True,
            point_in_time_verified=True,
            leakage_checks_passed=True,
            out_of_sample_folds=8,
            mae_improvement=0.12,
            rmse_improvement=0.10,
            positive_fold_share=0.50,
            worst_fold_improvement=-0.35,
        )
        self.assertFalse(decision.promotable)
        self.assertIn("insufficient_fold_stability", decision.reasons)
        self.assertIn("worst_fold_degradation_too_large", decision.reasons)

    def test_probability_candidate_requires_calibration(self) -> None:
        decision = evaluate_probability_promotion(
            dataset_ready=True,
            point_in_time_verified=True,
            leakage_checks_passed=True,
            out_of_sample_folds=10,
            brier_skill_score=0.10,
            positive_fold_share=0.8,
            worst_fold_improvement=-0.05,
            calibration_error=0.15,
        )
        self.assertFalse(decision.promotable)
        self.assertIn("calibration_error_above_threshold", decision.reasons)


if __name__ == "__main__":
    unittest.main()
