from __future__ import annotations

import unittest

from models.first_backtests import balance_identity_backtest, export30_backtest, yield_backtest


class FirstBacktestsTests(unittest.TestCase):
    def test_yield_backtest(self) -> None:
        result = yield_backtest([3000, 3100, 3050, 3200, 3300, 3350, 3400, 3450], min_train=5)
        self.assertEqual(result.model_id, "ALMT-SOY-YIELD-001")
        self.assertEqual(len(result.folds), 3)
        self.assertIn("moving_average_5_seasons", result.metrics)

    def test_balance_identity(self) -> None:
        result = balance_identity_backtest([{
            "opening_stock": 10, "production": 100, "inflows": 0,
            "crush": 20, "exports": 70, "other_outflows": 5, "ending_stock": 15,
        }])
        self.assertEqual(result.metrics["accounting_identity"]["mae"], 0)

    def test_export30_backtest(self) -> None:
        values = [float(100 + (i % 12) * 10 + i) for i in range(72)]
        result = export30_backtest(values, seasonal_period=12, min_years=5)
        self.assertEqual(len(result.folds), 12)
        self.assertIn("same_period_last_year", result.metrics)

    def test_export30_requires_history(self) -> None:
        with self.assertRaises(ValueError):
            export30_backtest([1.0] * 20, seasonal_period=12, min_years=5)


if __name__ == "__main__":
    unittest.main()
