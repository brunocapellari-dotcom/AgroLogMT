from __future__ import annotations

import unittest

from models.agrolog_360_marts import build_agrolog360_sql_bundle, climate_rollups_sql


class AgroLog360MartTests(unittest.TestCase):
    def test_bundle_has_unique_ids_and_canonical_dataset(self) -> None:
        bundle = build_agrolog360_sql_bundle("agrolog-prod")
        ids = [item.mart_id for item in bundle]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(bundle), 6)
        self.assertTrue(all("marts_agrolog360" in item.target for item in bundle))

    def test_climate_windows_are_present(self) -> None:
        sql = climate_rollups_sql("agrolog-prod").sql
        for token in ("chuva_7d_mm", "chuva_15d_mm", "chuva_30d_mm", "chuva_60d_mm", "chuva_90d_mm"):
            self.assertIn(token, sql)

    def test_rejects_unsafe_project_identifier(self) -> None:
        with self.assertRaises(ValueError):
            climate_rollups_sql("x`; DROP TABLE y; --")


if __name__ == "__main__":
    unittest.main()
