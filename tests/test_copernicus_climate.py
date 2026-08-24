from __future__ import annotations

import unittest
from datetime import date

from collector.copernicus_climate import agera5_timeseries_request, era5_land_timeseries_request
from models.agroclimate import bucket_water_balance, growing_degree_days
from models.climate_crosscheck import compare


class CopernicusClimateTests(unittest.TestCase):
    def test_agera5_v2_contract(self) -> None:
        req = agera5_timeseries_request(latitude=-13.05, longitude=-55.91, start=date(2020,1,1), end=date(2020,1,2))
        self.assertEqual(req.dataset, "sis-agrometeorological-indicators-timeseries")
        self.assertEqual(req.evidence_subtype, "agera5_v2_reanalysis_downscaled")

    def test_era5_land_contract(self) -> None:
        req = era5_land_timeseries_request(latitude=-13.05, longitude=-55.91, start=date(2020,1,1), end=date(2020,1,2))
        self.assertEqual(req.dataset, "reanalysis-era5-land-timeseries")
        self.assertIn("volumetric_soil_water_layer_1", req.payload["variable"])

    def test_water_balance(self) -> None:
        rows = bucket_water_balance([("2026-01-01", 10, 4), ("2026-01-02", 0, 20)], storage_capacity_mm=10, initial_storage_mm=5)
        self.assertEqual(rows[0].storage_mm, 10)
        self.assertEqual(rows[0].surplus_mm, 1)
        self.assertEqual(rows[1].deficit_mm, 10)

    def test_gdd(self) -> None:
        self.assertEqual(growing_degree_days(10, 30, base_c=10), 10)

    def test_crosscheck(self) -> None:
        result = compare([1,2,3], [2,3,4])
        self.assertAlmostEqual(result.mean_bias, 1)
        self.assertAlmostEqual(result.mae, 1)


if __name__ == "__main__":
    unittest.main()
