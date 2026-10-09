from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OperationsAutomationTests(unittest.TestCase):
    def test_gate_diagnoser_uses_failed_logs(self) -> None:
        text = (ROOT / "scripts" / "diagnose_final_gate.py").read_text(encoding="utf-8")
        self.assertIn("--log-failed", text)
        self.assertIn("failed_steps", text)
        self.assertIn("signals", text)

    def test_runner_orphan_guard_is_label_scoped_and_non_destructive_by_default(self) -> None:
        text = (ROOT / "scripts" / "audit_gce_ci_orphans.sh").read_text(encoding="utf-8")
        self.assertIn("labels.agrolog-ci=true", text)
        self.assertIn('DELETE_ORPHANS="${DELETE_ORPHANS:-0}"'.replace("\\", ""), text)
        self.assertIn("MAX_AGE_MINUTES", text)
        self.assertIn("gcloud compute instances delete", text)


if __name__ == "__main__":
    unittest.main()
