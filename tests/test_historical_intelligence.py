from __future__ import annotations

import unittest
from datetime import date

from models.historical_intelligence import HistoricalPoint, compare_history


class HistoricalIntelligenceTests(unittest.TestCase):
    def test_comparison_preserves_previous_season_phase_and_distribution(self) -> None:
        rows = [
            HistoricalPoint(date(2025, 9, 1), 10, season="2025/26", phase="planting", vintage_id="a"),
            HistoricalPoint(date(2025, 10, 1), 20, season="2025/26", phase="planting", vintage_id="b"),
            HistoricalPoint(date(2026, 9, 1), 15, season="2026/27", phase="planting", vintage_id="c"),
            HistoricalPoint(date(2026, 10, 1), 30, season="2026/27", phase="planting", vintage_id="d"),
        ]
        result = compare_history(rows)
        self.assertEqual(result.previous, 15.0)
        self.assertEqual(result.season_start, 15.0)
        self.assertEqual(result.prior_season_same_phase, 20.0)
        self.assertEqual(result.delta_previous, 15.0)
        self.assertEqual(result.trend_direction, "RISING")
        self.assertIsNotNone(result.percentile)

    def test_zero_base_does_not_create_invalid_percentage(self) -> None:
        rows = [
            HistoricalPoint(date(2026, 9, 1), 0),
            HistoricalPoint(date(2026, 10, 1), 5),
        ]
        self.assertIsNone(compare_history(rows).delta_previous_pct)


if __name__ == "__main__":
    unittest.main()
