from __future__ import annotations

import json
import unittest
from pathlib import Path


class EditorialTaxonomyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(Path("contracts/editorial_taxonomy.v1.json").read_text(encoding="utf-8"))

    def test_safra_and_commercialization_are_non_overlapping_families(self) -> None:
        families = self.contract["families"]
        self.assertIn("SAFRA_PRODUCAO", families)
        self.assertIn("MERCADO_COMERCIALIZACAO", families)
        self.assertNotIn("comercializacao", families["SAFRA_PRODUCAO"]["includes"])
        self.assertIn("comercializacao", families["MERCADO_COMERCIALIZACAO"]["includes"])

    def test_santos_alone_cannot_close_multiport_gate(self) -> None:
        self.assertFalse(self.contract["gate_rules"]["santos_alone_is_multiport"])
        self.assertIn("Santos + Paranagua/Antonina + Arco Norte", self.contract["families"]["PORTOS_LINEUP"]["gate"])

    def test_programmed_is_never_realized_by_taxonomy(self) -> None:
        self.assertTrue(self.contract["gate_rules"]["programmed_is_not_realized"])


if __name__ == "__main__":
    unittest.main()
