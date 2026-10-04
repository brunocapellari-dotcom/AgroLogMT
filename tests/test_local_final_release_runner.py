from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalFinalReleaseRunnerTests(unittest.TestCase):
    def test_runner_reproduces_full_release_without_github_actions(self) -> None:
        path = ROOT / "scripts" / "finalize_agrolog_without_actions.sh"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")

        required = (
            "scripts/run_full_project_ci_local.sh",
            "zizmor --offline --persona=auditor --min-severity=medium",
            "/tmp/gitleaks git --redact",
            "trivy fs",
            "trivy image",
            "syft dir:.",
            "docker build --pull --tag agrolog-collector:gate",
            "docker build --pull --file gateway/Dockerfile --tag agrolog-gateway:gate",
            "scripts/preflight_n6_gcp.sh",
            "scripts/homologate_n6_core.sh",
            "N6 CORE HOMOLOGATION: PASS",
            "scripts/run_bigquery_restore_drill.py",
            "scripts/validate_full_project.py --mode final",
            "scripts/final_release_auditor.py",
            "AGROLOG MT FINAL RELEASE: PASS",
        )
        for token in required:
            self.assertIn(token, text)

        for forbidden in ("gh workflow run", "gh run rerun", "workflow_dispatch"):
            self.assertNotIn(forbidden, text)

    def test_runner_pins_and_verifies_security_release_material(self) -> None:
        text = (ROOT / "scripts" / "finalize_agrolog_without_actions.sh").read_text(encoding="utf-8")
        for token in (
            "version='0.74.0'",
            "bc701c3c3ee8b9acbea2c23257e41381e3854888f51281616a6ba5dc96963821",
            "version='1.51.1'",
            "105346699e7cb694afa37a21e2386432df6278c99f71331c24b1e0bb0f38cc75",
            "sha256sum -c -",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
