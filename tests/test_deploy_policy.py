from __future__ import annotations

import unittest
from pathlib import Path


class DeployPolicyTests(unittest.TestCase):
    def test_scheduler_is_not_managed_by_recurrent_core_deploy(self) -> None:
        text = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('MANAGE_SCHEDULER="${MANAGE_SCHEDULER:-0}"', text)
        self.assertIn('if [[ "$MANAGE_SCHEDULER" != "0" ]]', text)
        self.assertNotIn("scheduler jobs create", text)
        self.assertNotIn("scheduler jobs update", text)

    def test_bigquery_write_roles_are_dataset_scoped_in_bootstrap_not_deploy(self) -> None:
        deploy = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        bootstrap = Path("scripts/setup_github_gcp_wif.sh").read_text(encoding="utf-8")

        self.assertNotIn("projects add-iam-policy-binding", deploy)
        self.assertNotIn("GRANT `roles/bigquery.dataEditor`", deploy)
        self.assertIn('ensure_project_role "$COLLECTOR_SA_EMAIL" roles/bigquery.user', bootstrap)
        self.assertIn('ensure_dataset_role "$dataset" "$COLLECTOR_SA_EMAIL" roles/bigquery.dataEditor', bootstrap)
        self.assertNotIn('ensure_project_role "$COLLECTOR_SA_EMAIL" roles/bigquery.admin', bootstrap)


if __name__ == "__main__":
    unittest.main()
