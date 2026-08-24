from __future__ import annotations

import json
import unittest
from pathlib import Path


class ImeaOperationalContractTests(unittest.TestCase):
    def test_contract_preserves_freight_semantics(self) -> None:
        data = json.loads(Path("contracts/imea_operational.v1.json").read_text(encoding="utf-8"))
        self.assertIn("frete IMEA e referencia publicada, nao frete efetivamente negociado", data["rules"])
        self.assertEqual(data["sheets"]["frete"], "logistica.imea_frete_referencia")


if __name__ == "__main__":
    unittest.main()
