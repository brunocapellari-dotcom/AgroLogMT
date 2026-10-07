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
        self.assertIn('AGRO_DATASET', text)
        self.assertIn('remove_legacy_project_role "$DEPLOYER_SA_EMAIL" "$role"', text)

    def test_agro_dataset_is_required_before_recurring_collector_deploy(self) -> None:
        deploy = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        preflight = Path("scripts/preflight_n6_gcp.sh").read_text(encoding="utf-8")
        self.assertIn('AGRO_DATASET="${AGRO_DATASET:-agro}"', deploy)
        self.assertIn('AGROLOG_AGRO_DATASET=${AGRO_DATASET}', deploy)
        self.assertIn('AGRO_DATASET="${AGRO_DATASET:-agro}"', preflight)

    def test_freight_ingest_isolated_from_read_only_gateway(self) -> None:
        gateway = Path("gateway/app.py").read_text(encoding="utf-8")
        freight_app = Path("gateway/freight_app.py").read_text(encoding="utf-8")
        bootstrap = Path("scripts/setup_github_gcp_wif.sh").read_text(encoding="utf-8")
        deploy = Path("scripts/deploy_freight_ingest_gcloud.sh").read_text(encoding="utf-8")

        self.assertNotIn("create_freight_router", gateway)
        self.assertIn("create_freight_router", freight_app)
        self.assertIn("agrolog-freight-ingest", bootstrap)
        self.assertIn("ON TABLE", bootstrap)
        self.assertIn("roles/bigquery.dataEditor", bootstrap)
        self.assertIn("--no-allow-unauthenticated", deploy)
        self.assertIn("AGROLOG_FREIGHT_SHARED_SECRET=", deploy)
        self.assertIn("--startup-probe", deploy)
        self.assertIn("--readiness-probe", deploy)
        self.assertIn("--liveness-probe", deploy)
        self.assertNotIn("gcloud projects add-iam-policy-binding", deploy)


if __name__ == "__main__":
    unittest.main()
