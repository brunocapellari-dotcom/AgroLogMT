from __future__ import annotations

import unittest
from pathlib import Path


class DeployPolicyTests(unittest.TestCase):
    def test_recurring_deploy_refuses_scheduler_mutation(self) -> None:
        text = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('MANAGE_SCHEDULER="${MANAGE_SCHEDULER:-0}"', text)
        self.assertIn('if [[ "$MANAGE_SCHEDULER" != "0" ]]', text)
        self.assertIn('deploy recorrente não gerencia Cloud Scheduler/IAM', text)

    def test_recurring_deploy_does_not_mutate_project_iam(self) -> None:
        text = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        self.assertNotIn('gcloud projects add-iam-policy-binding', text)
        self.assertNotIn('roles/bigquery.admin', text)
        self.assertNotIn('roles/bigquery.dataEditor', text)

    def test_bootstrap_owns_dataset_scoped_bigquery_roles(self) -> None:
        text = Path("scripts/setup_github_gcp_wif.sh").read_text(encoding="utf-8")
        self.assertIn('roles/bigquery.user', text)
        self.assertIn('roles/bigquery.dataEditor', text)
        self.assertIn('ensure_dataset_role', text)
        self.assertIn('MARITIME_DATASET', text)
        self.assertIn('remove_legacy_project_role "$DEPLOYER_SA_EMAIL" "$role"', text)


if __name__ == "__main__":
    unittest.main()
