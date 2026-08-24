from __future__ import annotations

import unittest

from models.intermediate_marts import build_sql_bundle, storage_sql, trade_sql, yield_target_sql


class IntermediateMartsTests(unittest.TestCase):
    def test_storage_uses_latest_canonical_geo(self) -> None:
        sql = storage_sql("project-abc").sql
        self.assertIn("referencia.v_municipios_ibge_latest", sql)
        self.assertIn("a.uf='MT'", sql)

    def test_trade_rejects_invalid_ncm(self) -> None:
        with self.assertRaises(ValueError):
            trade_sql("project-abc", soybean_ncm_codes=("12019",))

    def test_bundle_contains_five_marts(self) -> None:
        bundle = build_sql_bundle("project-abc", soybean_ncm_codes=("12011000", "12019000"))
        self.assertEqual(len(bundle), 5)
        self.assertEqual({x.mart_id for x in bundle}, {
            "soy_mt_production", "soy_mt_storage", "soy_mt_market", "soy_mt_trade", "soy_mt_climate"
        })

    def test_yield_target_is_separate_from_five_operational_blocks(self) -> None:
        target = yield_target_sql("project-abc")
        self.assertEqual(target.mart_id, "soy_mt_yield_target")
        self.assertEqual(target.target, "marts_soy_mt.yield_target_v1")
        self.assertIn("ibge_pam_soy_mt_yield", target.sql)
        self.assertIn("point_in_time_feature_eligible=FALSE", target.sql)
        self.assertIn("realized_label_not_point_in_time_feature", target.sql)


if __name__ == "__main__":
    unittest.main()
