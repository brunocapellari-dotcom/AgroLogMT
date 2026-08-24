from __future__ import annotations

import unittest

from collector.conab_safra import canonical_product_id, parse_product_table_sheet, select_current
from collector.xlsx_reader import XlsxSheet


class ConabSafraParserTests(unittest.TestCase):
    def _sheet(self) -> XlsxSheet:
        return XlsxSheet(
            name="MT",
            rows=[
                ["PRODUTO", "ÁREA (Em mil ha)", None, None, "PRODUTIVIDADE (Em kg/ha)", None, None, "PRODUÇÃO (Em mil t)"],
                [None, "Safra 24/25", "Safra 25/26", "VAR. %", "Safra 24/25", "Safra 25/26", "VAR. %", "Safra 24/25", "Safra 25/26", "VAR. %"],
                [None, "(a)", "(b)", "(b/a)", "(c)", "(d)", "(d/c)", "(e)", "(f)", "(f/e)"],
                ["SOJA", 13000.0, 13200.0, 1.5, 3500.0, 3600.0, 2.9, 45500.0, 47520.0, 4.4],
                ["MILHO 2ª SAFRA", 7000.0, 7200.0, 2.9, 6000.0, 6100.0, 1.7, 42000.0, 43920.0, 4.6],
                ["nota sem dados", None, None, None, None, None, None, None, None, None],
            ],
        )

    def test_parses_previous_and_current_vintage(self) -> None:
        records = parse_product_table_sheet(self._sheet(), geo_level="uf", geo_id="MT")
        self.assertEqual(len(records), 4)
        soy = select_current(records, geo_id="MT", product_id="soja")
        self.assertEqual(soy.safra, "25/26")
        self.assertEqual(soy.area_mil_ha, 13200.0)
        self.assertEqual(soy.produtividade_kg_ha, 3600.0)
        self.assertEqual(soy.producao_mil_t, 47520.0)
        self.assertEqual(soy.quality_flags, ())

    def test_product_normalization(self) -> None:
        self.assertEqual(canonical_product_id("SOJA"), "soja")
        self.assertEqual(canonical_product_id("ALGODÃO - PLUMA"), "algodao_pluma")
        self.assertEqual(canonical_product_id("MILHO 2ª SAFRA"), "milho_2_safra")

    def test_identity_quality_gate(self) -> None:
        sheet = self._sheet()
        rows = [list(r) for r in sheet.rows]
        rows[3][8] = 40000.0
        records = parse_product_table_sheet(XlsxSheet(name="MT", rows=rows), geo_level="uf", geo_id="MT")
        soy = select_current(records, geo_id="MT", product_id="soja")
        self.assertIn("area_yield_production_identity_gt_2pct", soy.quality_flags)
        self.assertLess(soy.quality_score, 1.0)


if __name__ == "__main__":
    unittest.main()
