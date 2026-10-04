from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitleaksAllowlistTests(unittest.TestCase):
    def test_false_positive_allowlists_are_narrow_and_keep_default_rules(self) -> None:
        text = (ROOT / ".gitleaks.toml").read_text(encoding="utf-8")

        self.assertIn("useDefault = true", text)
        self.assertIn('targetRules = ["private-key"]', text)
        self.assertIn("78137d1c058712a33dd8b3d2c8bc62de8af6904f", text)

        self.assertIn('targetRules = ["grafana-api-key"]', text)
        self.assertIn('condition = "AND"', text)
        self.assertIn('regexTarget = "line"', text)
        self.assertIn("diagnose|extract", text)
        self.assertIn("powerbi", text.lower())

        # Do not weaken the scanner globally by disabling built-in secret rules.
        self.assertNotIn("disabledRules", text)


if __name__ == "__main__":
    unittest.main()
