from __future__ import annotations

import unittest
from pathlib import Path


class MaritimeFinalSecurityIntegrationTests(unittest.TestCase):
    def text(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def test_production_bootstrap_requires_whole_project_gate(self) -> None:
        text = self.text("scripts/bootstrap_production_security.sh")
        self.assertIn("Whole project deterministic gate", text)
        self.assertIn("scripts/harden_github_repository.sh", text)
        self.assertIn("scripts/setup_github_gcp_wif.sh", text)
        self.assertIn("--public-access-prevention=enforced", text)
        self.assertIn("--managed-by=user", text)
        self.assertIn("scripts/preflight_n6_gcp.sh", text)

    def test_wif_uses_immutable_repository_ids(self) -> None:
        text = self.text("scripts/setup_github_gcp_wif.sh")
        self.assertIn("repository_id", text)
        self.assertIn("repository_owner_id", text)
        self.assertIn("refs/heads/main", text)
        self.assertNotIn("--allow-unauthenticated", text)

    def test_github_actions_is_not_the_recurring_ais_scheduler(self) -> None:
        text = self.text(".github/workflows/maritime-ais-hourly.yml")
        self.assertIn("workflow_dispatch", text)
        self.assertNotIn("schedule:", text)
        self.assertIn("Cloud Scheduler", text)

    def test_ais_deploy_is_deliberate_and_preflighted(self) -> None:
        text = self.text(".github/workflows/maritime-ais-deploy.yml")
        self.assertIn("workflow_dispatch", text)
        self.assertNotIn("push:", text)
        self.assertIn("scripts/preflight_n6_gcp.sh", text)
        self.assertIn("shipping_ais_capture_events", text)

    def test_gateway_has_cost_and_exposure_guards(self) -> None:
        text = self.text("scripts/deploy_gateway_gcloud.sh")
        for token in (
            "--max-instances",
            "--concurrency",
            "AGROLOG_BQ_MAX_BYTES_BILLED",
            "AGROLOG_BQ_QUERY_TIMEOUT_SECONDS",
            "allAuthenticatedUsers",
            "allUsers",
            "GATEWAY_SERVICE_ACCOUNT",
        ):
            self.assertIn(token, text)

    def test_final_validator_discovers_entire_test_tree(self) -> None:
        text = self.text("scripts/validate_full_project.py")
        self.assertIn('files(repo, "test*.py")', text)
        self.assertIn("tests_deterministic_all", text)
        self.assertIn("tests_live_all", text)
        self.assertIn("maritime_ui/package-lock.json", text)
        self.assertIn("npm", text)
        self.assertIn("ci", text)


if __name__ == "__main__":
    unittest.main()
