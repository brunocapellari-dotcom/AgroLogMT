from __future__ import annotations

import unittest

from models.project_release_gate import REQUIRED_RELEASE_STAGES
from scripts.final_release_auditor import AUDITOR_STAGE, audit


class FinalReleaseAuditorTests(unittest.TestCase):
    def _payload(self) -> dict:
        stages = []
        for name in REQUIRED_RELEASE_STAGES:
            status = "BLOCKED" if name == AUDITOR_STAGE else "PASS"
            evidence = [] if name == AUDITOR_STAGE else [f"evidence://{name}"]
            stages.append({"name": name, "status": status, "evidence": evidence, "details": {}})
        return {"status": "BLOCKED", "stages": stages}

    def test_auditor_passes_only_when_every_other_stage_passed(self) -> None:
        result = audit(self._payload())
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["pre_auditor_non_pass_stages"], [])

    def test_auditor_fails_when_any_prior_stage_is_blocked(self) -> None:
        payload = self._payload()
        item = next(stage for stage in payload["stages"] if stage["name"] == "backup_restore")
        item["status"] = "BLOCKED"
        item["evidence"] = []
        result = audit(payload)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("backup_restore", result["pre_auditor_non_pass_stages"])

    def test_auditor_fails_when_any_prior_stage_failed(self) -> None:
        payload = self._payload()
        item = next(stage for stage in payload["stages"] if stage["name"] == "secret_scan")
        item["status"] = "FAIL"
        item["evidence"] = []
        result = audit(payload)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("secret_scan", result["pre_auditor_non_pass_stages"])


if __name__ == "__main__":
    unittest.main()
