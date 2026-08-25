from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.hydrology import HydroObservation, NavigationEvent, contextualize_navigation, day_of_year_climatology, deltas_1_3_7_15, observed_delta

UTC = timezone.utc


class HydrologyTests(unittest.TestCase):
    def test_delta_requires_real_endpoints_and_never_interpolates(self) -> None:
        rows = [
            HydroObservation("15400000", "2026-08-24T12:00:00+00:00", river_level_cm=500),
            HydroObservation("15400000", "2026-08-25T12:00:00+00:00", river_level_cm=510),
        ]
        result = observed_delta(rows, station_code="15400000", field="river_level_cm", as_of=datetime(2026, 8, 25, 12, tzinfo=UTC), days=1)
        self.assertEqual(result["status"], "OBSERVED_DELTA")
        self.assertEqual(result["delta"], 10)
        self.assertFalse(result["interpolated"])

    def test_missing_endpoint_returns_data_gap(self) -> None:
        rows = [HydroObservation("15400000", "2026-08-25T12:00:00+00:00", river_level_cm=510)]
        result = observed_delta(rows, station_code="15400000", field="river_level_cm", as_of=datetime(2026, 8, 25, 12, tzinfo=UTC), days=1)
        self.assertEqual(result["status"], "DATA_GAP")
        self.assertIsNone(result["delta"])

    def test_standard_delta_windows_are_fixed(self) -> None:
        rows = [HydroObservation("X", f"2026-08-{day:02d}T12:00:00+00:00", river_level_cm=float(day)) for day in range(10, 26)]
        result = deltas_1_3_7_15(rows, station_code="X", field="river_level_cm", as_of=datetime(2026, 8, 25, 12, tzinfo=UTC))
        self.assertEqual([item["days"] for item in result], [1, 3, 7, 15])

    def test_climatology_requires_multiple_years(self) -> None:
        rows = [HydroObservation("X", f"{year}-01-15T12:00:00+00:00", river_level_cm=float(year - 2000)) for year in range(2020, 2025)]
        result = day_of_year_climatology(rows, station_code="X", field="river_level_cm", minimum_years=5)
        self.assertEqual(result[0]["status"], "READY")
        self.assertIsNotNone(result[0]["p50"])

    def test_river_level_does_not_infer_navigation_restriction(self) -> None:
        event = NavigationEvent("e1", "Madeira", "2026-08-25T10:00:00+00:00", "boletim", "normal", "https://official.example", False)
        result = contextualize_navigation(hydro_summary={"level_cm": 100}, events=[event], river_or_corridor="Madeira", as_of=datetime(2026, 8, 25, 12, tzinfo=UTC))
        self.assertFalse(result["restriction_observed"])
        self.assertFalse(result["restriction_inferred_from_hydrology"])


if __name__ == "__main__":
    unittest.main()
