from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GceRunnerScriptsTests(unittest.TestCase):
    def test_provisioner_preserves_ephemeral_least_privilege_baseline(self) -> None:
        text = (ROOT / "scripts" / "create_gce_ephemeral_runner.sh").read_text(encoding="utf-8")
        self.assertIn('RUNNER_COUNT="${RUNNER_COUNT:-2}"'.replace("\\", ""), text)
        self.assertIn("--ephemeral", text)
        self.assertIn("--no-service-account", text)
        self.assertIn("--no-scopes", text)
        self.assertIn("--shielded-secure-boot", text)
        self.assertIn("--shielded-vtpm", text)
        self.assertIn("gcp-ephemeral", text)
        self.assertIn("ZONE_CANDIDATES", text)
        self.assertIn("MACHINE_TYPE_CANDIDATES", text)

    def test_cleanup_discovers_labeled_runners_across_zones(self) -> None:
        text = (ROOT / "scripts" / "cleanup_gce_ci_runners.sh").read_text(encoding="utf-8")
        self.assertIn("gcloud compute instances list", text)
        self.assertIn("labels.agrolog-ci=true", text)
        self.assertIn("zone.basename()", text)
        self.assertNotIn('ZONE="${ZONE:-southamerica-east1-b}"'.replace("\\", ""), text)

    def test_release_controller_dispatches_final_gate_before_provisioning(self) -> None:
        text = (ROOT / "scripts" / "kick_final_release_gce.sh").read_text(encoding="utf-8")
        dispatch = text.index('gh workflow run "$WORKFLOW"')
        provision = text.index("bash scripts/create_gce_ephemeral_runner.sh")
        self.assertLess(dispatch, provision)
        self.assertIn("-f final_release=true", text)
        self.assertIn('--branch "$BRANCH"', text)


if __name__ == "__main__":
    unittest.main()
