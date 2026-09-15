from __future__ import annotations

import unittest

from models.pecuaria_trade import build_create_view_sql, build_mt_beef_export_query, load_beef_scope


class PecuariaTradeTests(unittest.TestCase):
    def test_contract_scope_partitions_current_beef_codes(self) -> None:
        scope = load_beef_scope()
        self.assertEqual(len(scope["ncm8"]), 10)
        self.assertEqual(len(scope["segments"]["fresca_refrigerada"]), 5)
        self.assertEqual(len(scope["segments"]["congelada"]), 5)
        self.assertTrue(scope["offal_excluded"])
        self.assertEqual(set(scope["historical_aggregate"]["headings"]), {"0201", "0202"})

    def test_query_uses_hs4_history_and_mt_semantics(self) -> None:
        sql = build_mt_beef_export_query(project_id="agrolog-prod", end_year=2026)
        self.assertIn("`agrolog-prod.comercio_exterior.comexstat_ncm_export`", sql)
        self.assertIn("sg_uf_ncm = 'MT'", sql)
        self.assertIn("co_ano >= 1997", sql)
        self.assertIn("co_ano <= 2026", sql)
        self.assertIn("STARTS_WITH(co_ncm, '0201')", sql)
        self.assertIn("STARTS_WITH(co_ncm, '0202')", sql)
        self.assertIn("fresca_refrigerada", sql)
        self.assertIn("congelada", sql)
        self.assertIn("ANY_VALUE(urf_semantics)", sql)
        self.assertNotIn("02061000", sql)
        self.assertNotIn("co_ncm IN ('02011000'", sql)

    def test_historical_query_refuses_pre_comex_period(self) -> None:
        with self.assertRaises(ValueError):
            build_mt_beef_export_query(project_id="agrolog-prod", start_year=1996)

    def test_create_view_is_deterministic_and_identifier_safe(self) -> None:
        sql = build_create_view_sql(project_id="agrolog-prod")
        self.assertTrue(sql.startswith("CREATE OR REPLACE VIEW"))
        self.assertIn("v_pecuaria_mt_beef_exports", sql)
        with self.assertRaises(ValueError):
            build_create_view_sql(project_id="bad.project")


if __name__ == "__main__":
    unittest.main()
