from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "evaluate_bandit_report.py"


class BanditPolicyTests(unittest.TestCase):
    def run_policy(self, results: list[dict]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "bandit.json"
            report.write_text(json.dumps({"results": results}), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(report)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_passes_empty_report(self) -> None:
        result = self.run_policy([])
        self.assertEqual(result.returncode, 0)
        self.assertIn("BANDIT_BLOCKING_COUNT=0", result.stdout)

    def test_blocks_medium_high_confidence_finding(self) -> None:
        result = self.run_policy([
            {
                "filename": "collector/example.py",
                "line_number": 10,
                "test_id": "B310",
                "issue_severity": "MEDIUM",
                "issue_confidence": "HIGH",
                "issue_text": "unsafe urlopen",
            }
        ])
        self.assertEqual(result.returncode, 1)
        self.assertIn("BANDIT_BLOCKING_COUNT=1", result.stdout)
        self.assertIn("collector/example.py:10 B310", result.stdout)

    def test_ignores_low_severity_or_low_confidence(self) -> None:
        result = self.run_policy([
            {
                "filename": "x.py",
                "line_number": 1,
                "test_id": "B101",
                "issue_severity": "LOW",
                "issue_confidence": "HIGH",
                "issue_text": "low",
            },
            {
                "filename": "y.py",
                "line_number": 2,
                "test_id": "B999",
                "issue_severity": "MEDIUM",
                "issue_confidence": "LOW",
                "issue_text": "low confidence",
            },
        ])
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
