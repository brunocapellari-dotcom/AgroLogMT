from __future__ import annotations

import json
import unittest
from pathlib import Path


CONTRACT_PATH = Path("contracts/product_trade_codes.v1.json")
EXPECTED_BEEF_NCM = {
    "02011000", "02012010", "02012020", "02012090", "02013000",
    "02021000", "02022010", "02022020", "02022090", "02023000",
}


class ProductTradeCodesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_beef_current_scope_is_explicit_and_complete(self) -> None:
        beef = self.contract["products"]["carne_bovina_in_natura"]
        self.assertEqual(set(beef["ncm8"]), EXPECTED_BEEF_NCM)
        self.assertEqual(
            set(beef["segments"]["fresca_refrigerada"])
            | set(beef["segments"]["congelada"]),
            EXPECTED_BEEF_NCM,
        )
        self.assertTrue(beef["offal_excluded"])
        self.assertEqual(beef["flow"], "export")

    def test_beef_historical_aggregate_uses_hs4_not_current_ncm8(self) -> None:
        beef = self.contract["products"]["carne_bovina_in_natura"]
        historical = beef["historical_aggregate"]
        self.assertEqual(historical["basis"], "hs4_heading")
        self.assertEqual(set(historical["headings"]), {"0201", "0202"})
        self.assertEqual(historical["segment_by_heading"]["0201"], "fresca_refrigerada")
        self.assertEqual(historical["segment_by_heading"]["0202"], "congelada")
        self.assertTrue(historical["ncm8_temporal_mapping_required"])
        self.assertTrue(historical["observed_ncm_audit_required"])

    def test_beef_descriptions_cover_every_current_code(self) -> None:
        beef = self.contract["products"]["carne_bovina_in_natura"]
        self.assertEqual(set(beef["descriptions"]), EXPECTED_BEEF_NCM)

    def test_contract_keeps_offal_and_ncm8_history_guardrails(self) -> None:
        rules = " ".join(self.contract["rules"])
        self.assertIn("HS4 0201 e 0202", rules)
        self.assertIn("NCM8", rules)
        self.assertIn("miudezas", rules)


if __name__ == "__main__":
    unittest.main()
