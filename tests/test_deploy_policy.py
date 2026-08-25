from __future__ import annotations

import unittest
from pathlib import Path


class DeployPolicyTests(unittest.TestCase):
    def test_scheduler_is_opt_in_during_p0(self) -> None:
        text = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('MANAGE_SCHEDULER="${MANAGE_SCHEDULER:-0}"', text)
        self.assertIn('if [[ "${MANAGE_SCHEDULER}" == "1" ]]', text)

    def test_bigquery_write_roles_are_dataset_scoped(self) -> None:
        text = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('roles/bigquery.user', text)
        self.assertIn('roles/bigquery.dataEditor', text)
        self.assertNotIn('roles/bigquery.admin', text)


if __name__ == "__main__":
    unittest.main()
