from __future__ import annotations

import unittest

from collector.weather_forecast_ingest import normalize_forecast_row


class WeatherForecastIngestTests(unittest.TestCase):
    def test_preserves_run_identity_and_member(self) -> None:
        row = normalize_forecast_row({
            "source_id": "ecmwf_open_data",
            "model": "IFS",
            "run_id": "20261007T12Z",
            "initialization_time": "2026-10-07T12:00:00Z",
            "forecast_hour": 24,
            "valid_time": "2026-10-08T12:00:00Z",
            "collection_time": "2026-10-07T15:00:00Z",
            "geo_id": "MT",
            "resolution": "0.25deg",
            "ensemble_member": "control",
            "variable": "tp",
            "value": 12.3,
            "unit": "mm",
        })
        self.assertEqual(row.ensemble_member, "control")
        self.assertEqual(row.evidence_class, "PREVISTO")
        self.assertEqual(len(row.record_id), 64)

    def test_rejects_invalid_valid_time(self) -> None:
        with self.assertRaises(ValueError):
            normalize_forecast_row({
                "source_id": "gfs", "model": "GFS", "run_id": "r",
                "initialization_time": "2026-10-07T00:00:00Z", "forecast_hour": 24,
                "valid_time": "2026-10-09T00:00:00Z", "collection_time": "2026-10-07T01:00:00Z",
                "variable": "tp", "value": 1, "unit": "mm",
            })


if __name__ == "__main__":
    unittest.main()
