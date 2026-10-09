from __future__ import annotations

import unittest

from models.analog_years import find_analog_years


class AnalogYearsTests(unittest.TestCase):
    def test_finds_nearest_year_with_standardized_features(self) -> None:
        current = {"rain": 100.0, "temp": 28.0, "soil": 45.0}
        history = {
            "2018": {"rain": 95.0, "temp": 28.2, "soil": 44.0},
            "2019": {"rain": 50.0, "temp": 31.0, "soil": 20.0},
            "2020": {"rain": 110.0, "temp": 27.5, "soil": 48.0},
            "2021": {"rain": 80.0, "temp": 29.0, "soil": 35.0},
            "2022": {"rain": 130.0, "temp": 27.0, "soil": 55.0},
        }
        result = find_analog_years(current, history)
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.candidates[0].year, "2018")

    def test_rejects_short_history(self) -> None:
        result = find_analog_years({"a": 1, "b": 2, "c": 3}, {"2025": {"a": 1, "b": 2, "c": 3}})
        self.assertEqual(result.status, "REJECTED")


if __name__ == "__main__":
    unittest.main()
