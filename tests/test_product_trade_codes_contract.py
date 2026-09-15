from __future__ import annotations

import json
import unittest
from pathlib import Path


CONTRACT_PATH = Path("contracts/product_trade_codes.v1.json")
EXPECTED_BEEF_NCM = {
    "02011000",
    "02012010",
    "02012020",
    "02012090",
    "02013000",
    "02021000",
    "02022010",
    "02022020",
    "02022090",
    "02023000",
}


class ProductTradeCodesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_beef_in_natura_scope_is_explicit_and_complete(self) -> None:
        beef = self.contract["products"]["carne_bovina_in_natura"]
        self.assertEqual(set(beef["ncm8"]), EXPECTED_BEEF_NCM)
        self.assertEqual(
            set(beef["segments"]["fresca_refrigerada"])
            | set(beef["segments"]["congelada"]),
            EXPECTED_BEEF_NCM,
        )
        self.assertTrue(beef["offal_excluded"])
        self.assertTrue(beef["historical_mapping_required"])
        self.assertEqual(beef["flow"], "export")

    def test_beef_descriptions_cover_every_code(self) -> None:
        beef = self.contract["products"]["carne_bovina_in_natura"]
        self.assertEqual(set(beef["descriptions"]), EXPECTED_BEEF_NCM)

    def test_contract_keeps_historical_mapping_guardrail(self) -> None:
        rules = " ".join(self.contract["rules"])
        self.assertIn("historical_mapping_required", rules)
        self.assertIn("miudezas", rules)


if __name__ == "__main__":
    unittest.main()
