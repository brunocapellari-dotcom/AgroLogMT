from __future__ import annotations

import unittest
from pathlib import Path

from gateway.pecuaria_queries import (
    build_beef_export_history_sql,
    build_beef_exports_sql,
    build_cattle_municipal_history_sql,
    build_cattle_state_history_sql,
    build_sigsif_current_sql,
    build_slaughter_quarterly_sql,
    load_beef_ncms,
)


class PecuariaGatewayQueryTests(unittest.TestCase):
    def test_gateway_uses_canonical_beef_contract(self) -> None:
        codes = load_beef_ncms(Path("contracts/product_trade_codes.v1.json"))
        self.assertEqual(len(codes), 10)
        self.assertIn("02013000", codes)
        self.assertIn("02023000", codes)
        self.assertNotIn("02061000", codes)

    def test_state_query_is_bounded_and_uses_state_view(self) -> None:
        sql = build_cattle_state_history_sql("agrolog-prod", "pecuaria")
        self.assertIn("v_ibge_ppm_cattle_mt_state_year", sql)
        self.assertIn("@year_start", sql)
        self.assertIn("@year_end", sql)
        self.assertIn("LIMIT @limit", sql)

    def test_municipal_query_preserves_temporal_flags(self) -> None:
        sql = build_cattle_municipal_history_sql("agrolog-prod", "pecuaria")
        self.assertIn("availability_verified", sql)
        self.assertIn("point_in_time_feature_eligible", sql)
        self.assertIn("@ibge_code", sql)
        self.assertIn("@municipio_pattern", sql)

    def test_slaughter_query_preserves_derived_weight_and_pit_guard(self) -> None:
        sql = build_slaughter_quarterly_sql("agrolog-prod", "pecuaria")
        self.assertIn("v_ibge_slaughter_cattle_mt_quarterly", sql)
        self.assertIn("peso_medio_carcaca_kg_cabeca", sql)
        self.assertIn("historical_pit_guard_preserved", sql)
        self.assertIn("@quarter", sql)
        self.assertIn("LIMIT @limit", sql)

    def test_sigsif_query_exposes_snapshot_temporal_semantics(self) -> None:
        sql = build_sigsif_current_sql("agrolog-prod", "pecuaria")
        self.assertIn("v_mapa_sigsif_slaughter_snapshot_mt_summary", sql)
        self.assertIn("participacao_femeas", sql)
        self.assertIn("temporal_semantics", sql)
        self.assertNotIn("GROUP BY", sql.upper())

    def test_beef_current_query_is_read_only_and_semantically_scoped(self) -> None:
        sql = build_beef_exports_sql("agrolog-prod", "comercio_exterior")
        self.assertIn("v_comexstat_trade_monthly_latest", sql)
        self.assertIn("state_name = 'Mato Grosso'", sql)
        self.assertIn("flow = 'export'", sql)
        self.assertIn("ncm_code IN UNNEST(@ncms)", sql)
        self.assertNotIn("DELETE ", sql.upper())
        self.assertNotIn("UPDATE ", sql.upper())
        self.assertNotIn("INSERT ", sql.upper())

    def test_beef_history_query_uses_hs4_view_not_current_ncm_list(self) -> None:
        sql = build_beef_export_history_sql("agrolog-prod", "comercio_exterior")
        self.assertIn("v_pecuaria_mt_beef_exports", sql)
        self.assertIn("@year_start", sql)
        self.assertIn("@segmento", sql)
        self.assertNotIn("UNNEST(@ncms)", sql)
        self.assertNotIn("02011000", sql)

    def test_identifiers_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            build_beef_exports_sql("bad.project", "comercio_exterior")
        with self.assertRaises(ValueError):
            build_slaughter_quarterly_sql("agrolog-prod", "bad.dataset")


if __name__ == "__main__":
    unittest.main()
