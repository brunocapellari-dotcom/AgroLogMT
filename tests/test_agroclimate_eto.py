from __future__ import annotations

import unittest

from models.agroclimate import (
    bucket_water_balance,
    extraterrestrial_radiation_mj_m2_day,
    hargreaves_samani_eto_mm,
    summarize_water_balance,
)


class AgroclimateEtoTests(unittest.TestCase):
    def test_extraterrestrial_radiation_is_physical_and_latitude_sensitive(self) -> None:
        ra_mt = extraterrestrial_radiation_mj_m2_day(latitude_deg=-13.0, day_of_year=200)
        ra_high_lat = extraterrestrial_radiation_mj_m2_day(latitude_deg=-45.0, day_of_year=200)
        self.assertGreater(ra_mt, 0.0)
        self.assertGreater(ra_high_lat, 0.0)
        self.assertNotAlmostEqual(ra_mt, ra_high_lat)

    def test_hargreaves_eto_is_positive_and_responds_to_thermal_range(self) -> None:
        mild = hargreaves_samani_eto_mm(tmin_c=20, tmax_c=30, tmean_c=25, latitude_deg=-13, day_of_year=200)
        hot_range = hargreaves_samani_eto_mm(tmin_c=18, tmax_c=36, tmean_c=27, latitude_deg=-13, day_of_year=200)
        self.assertGreater(mild, 0.0)
        self.assertGreater(hot_range, mild)

    def test_bucket_summary_keeps_deficit_and_surplus_separate(self) -> None:
        rows = bucket_water_balance(
            [("2026-01-01", 0.0, 8.0), ("2026-01-02", 0.0, 8.0), ("2026-01-03", 50.0, 4.0)],
            storage_capacity_mm=10.0,
            initial_storage_mm=5.0,
        )
        summary = summarize_water_balance(rows)
        self.assertEqual(summary.days, 3)
        self.assertGreater(summary.deficit_mm, 0.0)
        self.assertGreater(summary.surplus_mm, 0.0)
        self.assertGreater(summary.deficit_days, 0)
        self.assertGreater(summary.surplus_days, 0)


if __name__ == "__main__":
    unittest.main()
