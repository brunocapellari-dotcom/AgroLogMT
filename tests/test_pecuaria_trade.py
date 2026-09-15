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

    def test_query_uses_existing_comex_table_and_mt_semantics(self) -> None:
        sql = build_mt_beef_export_query(project_id="agrolog-prod", end_year=2026)
        self.assertIn("`agrolog-prod.comercio_exterior.comexstat_ncm_export`", sql)
        self.assertIn("sg_uf_ncm = 'MT'", sql)
        self.assertIn("co_ano >= 1997", sql)
        self.assertIn("co_ano <= 2026", sql)
        self.assertIn("ANY_VALUE(urf_semantics)", sql)
        self.assertNotIn("02061000", sql)
        for code in load_beef_scope()["ncm8"]:
            self.assertIn(code, sql)

    def test_create_view_is_deterministic_and_identifier_safe(self) -> None:
        sql = build_create_view_sql(project_id="agrolog-prod")
        self.assertTrue(sql.startswith("CREATE OR REPLACE VIEW"))
        self.assertIn("v_pecuaria_mt_beef_exports", sql)
        with self.assertRaises(ValueError):
            build_create_view_sql(project_id="bad.project")


if __name__ == "__main__":
    unittest.main()
