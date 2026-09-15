from __future__ import annotations

import unittest

from models.project_release_gate import REQUIRED_RELEASE_STAGES, ReleaseStage, evaluate_release, validate_manifest


class FullProjectReleaseGateTests(unittest.TestCase):
    def _pass_stages(self) -> list[ReleaseStage]:
        return [ReleaseStage(name=name, status="PASS", evidence=(f"evidence://{name}",), details={}) for name in REQUIRED_RELEASE_STAGES]

    def test_only_all_required_pass_stages_release_project(self) -> None:
        result = evaluate_release(self._pass_stages())
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["release_ready"])
        self.assertEqual(result["present_stage_count"], len(REQUIRED_RELEASE_STAGES))

    def test_one_blocked_stage_blocks_entire_release(self) -> None:
        stages = self._pass_stages()
        stages[3] = ReleaseStage(name=stages[3].name, status="BLOCKED", evidence=(), details={})
        result = evaluate_release(stages)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["release_ready"])

    def test_one_failure_fails_entire_release(self) -> None:
        stages = self._pass_stages()
        stages[4] = ReleaseStage(name=stages[4].name, status="FAIL", evidence=(), details={})
        result = evaluate_release(stages)
        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["release_ready"])

    def test_missing_stage_is_blocked_not_partial_pass(self) -> None:
        result = evaluate_release(self._pass_stages()[:-1])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(REQUIRED_RELEASE_STAGES[-1], result["missing_stages"])

    def test_pass_without_evidence_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "PASS stage requires evidence"):
            ReleaseStage.from_dict({"name": "repository_integrity", "status": "PASS", "evidence": []})

    def test_duplicate_stage_is_rejected(self) -> None:
        stages = self._pass_stages()
        with self.assertRaisesRegex(ValueError, "duplicate release stage"):
            evaluate_release(stages + [stages[0]])

    def test_declared_manifest_status_must_match_evaluation(self) -> None:
        payload = {
            "version": "1.0.0",
            "status": "PASS",
            "stages": [
                {"name": stage.name, "status": stage.status, "evidence": list(stage.evidence), "details": {}}
                for stage in self._pass_stages()
            ],
        }
        self.assertEqual(validate_manifest(payload)["status"], "PASS")
        payload["stages"][0]["status"] = "BLOCKED"
        payload["stages"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_manifest(payload)


if __name__ == "__main__":
    unittest.main()
