from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgroLog360HomologationTests(unittest.TestCase):
    def test_homologation_is_fail_closed_and_requires_core_marts(self) -> None:
        text = (ROOT / "scripts/homologate_agrolog360.sh").read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", text)
        self.assertIn("climate_rollups", text)
        self.assertIn("storage_balance", text)
        self.assertIn("overview_current", text)
        self.assertIn("AGROLOG 360 OPERATIONAL HOMOLOGATION: PASS", text)

    def test_gateway_validator_uses_https_guard(self) -> None:
        text = (ROOT / "scripts/validate_agrolog360_gateway.py").read_text(encoding="utf-8")
        self.assertIn("validate_https_url", text)
        self.assertIn("# nosec B310", text)


if __name__ == "__main__":
    unittest.main()
