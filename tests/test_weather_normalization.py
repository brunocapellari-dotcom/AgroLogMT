from __future__ import annotations

import unittest
from datetime import datetime, timezone

from collector.cptec_forecast import normalize_cptec_forecast
from collector.inmet_daily import normalize_inmet_daily_row


UTC = timezone.utc


class WeatherNormalizationTests(unittest.TestCase):
    def test_inmet_missing_values_remain_missing(self) -> None:
        row = normalize_inmet_daily_row(
            {"data": "2026-09-29", "precipitacao": "", "temp_min": "20,5", "temp_max": "34,2"},
            geo_id="5105259",
            collected_at=datetime(2026, 9, 29, 14, tzinfo=UTC),
        )
        self.assertIsNone(row.precipitacao_mm)
        self.assertIn("precipitation_missing", row.quality_flags)
        self.assertEqual(row.tmin_c, 20.5)
        self.assertEqual(row.evidence_class, "OBSERVADO")

    def test_cptec_forecast_is_never_observed(self) -> None:
        row = normalize_cptec_forecast(
            {"value": "18.5"},
            geo_id="MT",
            model_cycle_at="2026-09-29T00:00:00+00:00",
            valid_at="2026-09-30T00:00:00+00:00",
            variable="precipitation_mm",
            unit="mm",
            collected_at="2026-09-29T02:00:00+00:00",
        )
        self.assertEqual(row.lead_hours, 24)
        self.assertEqual(row.evidence_class, "PROJETADO")

    def test_cptec_valid_time_cannot_precede_cycle(self) -> None:
        with self.assertRaises(ValueError):
            normalize_cptec_forecast(
                {"value": 1},
                geo_id="MT",
                model_cycle_at="2026-09-30T00:00:00+00:00",
                valid_at="2026-09-29T00:00:00+00:00",
                variable="precipitation_mm",
                unit="mm",
            )


if __name__ == "__main__":
    unittest.main()
