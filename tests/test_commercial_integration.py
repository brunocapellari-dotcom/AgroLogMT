from __future__ import annotations

import unittest

from models.agrolog_360_marts import agricultural_exports_sql, crop_progress_current_sql, storage_balance_sql
from models.commercial_analysis import build_derived_components


class CommercialIntegrationTests(unittest.TestCase):
    def test_storage_uses_latest_current_lowercase_geo_level(self) -> None:
        sql = storage_balance_sql("agrolog-prod").sql
        self.assertIn("geo_level='uf'", sql)
        self.assertIn("vintage_position='current'", sql)
        self.assertIn("ROW_NUMBER()", sql)
        self.assertNotIn("geo_level='UF'", sql)

    def test_exports_use_canonical_ncm_contract_codes(self) -> None:
        sql = agricultural_exports_sql("agrolog-prod").sql
        for token in ("12011000", "12019000", "10059010", "23040010", "15071000"):
            self.assertIn(token, sql)
        self.assertIn("delta_toneladas_pct", sql)

    def test_crop_progress_preserves_previous_value(self) -> None:
        sql = crop_progress_current_sql("agrolog-prod").sql
        self.assertIn("LAG(valor)", sql)
        self.assertIn("delta_value", sql)

    def test_derived_analysis_keeps_freight_semantics(self) -> None:
        out = build_derived_components([{
            "component": "freight", "status": "FRESH", "data": [{
                "origin_municipality_id": "5107925",
                "destination_municipality_id": "5107602",
                "historical_percentile": 90,
            }]
        }])
        analysis = next(item for item in out if item["component"] == "analysis")
        self.assertIn("não equivale a frete contratado", analysis["data"][0]["summary"])


if __name__ == "__main__":
    unittest.main()
