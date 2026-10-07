from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.weather_multimodel import ForecastPoint, build_multimodel_consensus


class WeatherMultimodelTests(unittest.TestCase):
    def test_consensus_uses_latest_run_per_model_and_median_not_blind_mean(self) -> None:
        valid = datetime(2026, 10, 10, tzinfo=timezone.utc)
        r00 = datetime(2026, 10, 7, 0, tzinfo=timezone.utc)
        r12 = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
        rows = [
            ForecastPoint("ECMWF", r00, valid, "precip_72h", 30, "mm"),
            ForecastPoint("ECMWF", r12, valid, "precip_72h", 40, "mm"),
            ForecastPoint("GFS", r00, valid, "precip_72h", 20, "mm"),
            ForecastPoint("GFS", r12, valid, "precip_72h", 30, "mm"),
            ForecastPoint("ICON", r12, valid, "precip_72h", 100, "mm"),
        ]
        result = build_multimodel_consensus(rows, valid_at=valid, variable="precip_72h")
        self.assertEqual(result.model_count, 3)
        self.assertEqual(result.median_value, 40.0)
        self.assertEqual(result.direction, "UPWARD_REVISION")
        self.assertEqual(result.direction_agreement_share, 1.0)
        self.assertGreater(result.iqr, 0)

    def test_mixed_units_fail_closed(self) -> None:
        valid = datetime(2026, 10, 10, tzinfo=timezone.utc)
        run = datetime(2026, 10, 7, tzinfo=timezone.utc)
        rows = [
            ForecastPoint("ECMWF", run, valid, "temp", 30, "C"),
            ForecastPoint("GFS", run, valid, "temp", 86, "F"),
        ]
        with self.assertRaises(ValueError):
            build_multimodel_consensus(rows, valid_at=valid, variable="temp")


if __name__ == "__main__":
    unittest.main()
