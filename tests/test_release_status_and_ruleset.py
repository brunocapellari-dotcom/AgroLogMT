from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = "Whole project deterministic gate"


class ReleaseStatusAndRulesetTests(unittest.TestCase):
    def test_ruleset_requires_canonical_whole_project_context(self) -> None:
        text = (ROOT / "scripts" / "harden_github_repository.sh").read_text(encoding="utf-8")
        self.assertIn(f'REQUIRED_CHECK="${{REQUIRED_CHECK:-{CONTEXT}}}"', text)
        self.assertNotIn('REQUIRED_CHECK="${REQUIRED_CHECK:-unittest}"', text)

    def test_status_publisher_is_fail_closed_and_exact_commit_bound(self) -> None:
        text = (ROOT / "scripts" / "publish_full_project_status.sh").read_text(encoding="utf-8")
        for token in (
            CONTEXT,
            "N6 CORE HOMOLOGATION: PASS",
            "tested_commit",
            "git rev-parse HEAD",
            "state=success",
            "repos/${REPO}/statuses/${SHA}",
            "PASS GitHub commit status readback",
        ):
            self.assertIn(token, text)
        self.assertIn("obj.get('status')!='PASS'", text)
        self.assertIn("obj.get('tested_commit')!=sha", text)


if __name__ == "__main__":
    unittest.main()
