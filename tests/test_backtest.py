from __future__ import annotations

import unittest

from models.backtest import brier_score, regression_metrics, rolling_origin_splits


class BacktestTests(unittest.TestCase):
    def test_regression_metrics(self) -> None:
        metrics = regression_metrics([10.0, 20.0], [12.0, 18.0])
        self.assertEqual(metrics.mae, 2.0)
        self.assertAlmostEqual(metrics.rmse, 2.0)

    def test_brier(self) -> None:
        self.assertAlmostEqual(brier_score([1, 0], [0.8, 0.2]), 0.04)

    def test_rolling_origin_never_uses_future_in_train(self) -> None:
        splits = rolling_origin_splits(10, min_train=5, horizon=2, step=2)
        self.assertEqual(len(splits), 2)
        for train, test in splits:
            self.assertLess(max(train), min(test))


if __name__ == "__main__":
    unittest.main()
