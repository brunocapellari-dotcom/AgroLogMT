from __future__ import annotations

import unittest

from models.agrolog_360_marts import build_agrolog360_sql_bundle, crop_vintages_sql, freight_history_sql


class SellableMartsTests(unittest.TestCase):
    def test_bundle_includes_sellable_history_views(self) -> None:
        ids = {item.mart_id for item in build_agrolog360_sql_bundle("agrolog-prod")}
        self.assertIn("crop_vintages", ids)
        self.assertIn("crop_current", ids)
        self.assertIn("freight_history", ids)

    def test_crop_vintages_preserves_snapshot_and_uses_lag(self) -> None:
        sql = crop_vintages_sql("agrolog-prod").sql
        self.assertIn("snapshot_id", sql)
        self.assertIn("LAG(", sql)
        self.assertIn("delta_producao_pct", sql)

    def test_freight_history_has_7d_30d_and_percentile(self) -> None:
        sql = freight_history_sql("agrolog-prod").sql
        self.assertIn("freight_brl_per_t_avg_7d", sql)
        self.assertIn("freight_brl_per_t_avg_30d", sql)
        self.assertIn("historical_percentile", sql)


if __name__ == "__main__":
    unittest.main()
