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
        self.assertNotIn('gcloud services enable', text)
        self.assertNotIn('bq --location="$BQ_LOCATION" mk', text)

    def test_p0_deploy_is_also_non_administrative(self) -> None:
        text = Path("scripts/deploy_p0_connectors_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('MANAGE_SCHEDULER="${MANAGE_SCHEDULER:-0}"', text)
        self.assertIn('if [[ "$MANAGE_SCHEDULER" != "0" ]]', text)
        self.assertNotIn('gcloud services enable', text)
        self.assertNotIn('gcloud iam service-accounts create', text)
        self.assertNotIn('gcloud projects add-iam-policy-binding', text)
        self.assertNotIn('bq --location="${BQ_LOCATION}" mk', text)
        self.assertNotIn('gcloud scheduler jobs create', text)
        self.assertNotIn('gcloud scheduler jobs update', text)
        self.assertIn('--service-account "$BUILD_SERVICE_ACCOUNT"', text)
        self.assertIn('--gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source"', text)

    def test_bootstrap_owns_dataset_scoped_bigquery_roles(self) -> None:
        text = Path("scripts/setup_github_gcp_wif.sh").read_text(encoding="utf-8")
        self.assertIn('roles/bigquery.user', text)
        self.assertIn('roles/bigquery.dataEditor', text)
        self.assertIn('ensure_dataset_role', text)
        self.assertIn('MARITIME_DATASET', text)
        self.assertIn('AGRO_DATASET', text)
        self.assertIn('PECUARIA_DATASET', text)
        self.assertIn('remove_legacy_project_role "$DEPLOYER_SA_EMAIL" "$role"', text)

    def test_bootstrap_owns_scheduler_and_raw_reference_secret(self) -> None:
        bootstrap = Path("scripts/setup_github_gcp_wif.sh").read_text(encoding="utf-8")
        preflight = Path("scripts/preflight_n6_gcp.sh").read_text(encoding="utf-8")
        self.assertIn('SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"', bootstrap)
        self.assertIn('ensure_project_role "$SCHEDULER_SA_EMAIL" roles/run.invoker', bootstrap)
        self.assertIn('DRIVE_FOLDER_SECRET="${DRIVE_FOLDER_SECRET:-agrolog-drive-folder-id}"', bootstrap)
        self.assertIn('roles/secretmanager.secretAccessor', bootstrap)
        self.assertIn('SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"', preflight)
        self.assertIn('DRIVE_FOLDER_SECRET="${DRIVE_FOLDER_SECRET:-agrolog-drive-folder-id}"', preflight)
        self.assertIn("scheduler:'roles/run.invoker'", preflight)
        self.assertIn('gcloud secrets versions access latest', preflight)

    def test_deploys_resolve_raw_reference_without_hardcoded_id(self) -> None:
        for path in ("scripts/deploy_collectors_gcloud.sh", "scripts/deploy_p0_connectors_gcloud.sh"):
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn('DRIVE_FOLDER_SECRET="${DRIVE_FOLDER_SECRET:-agrolog-drive-folder-id}"', text)
            self.assertIn('gcloud secrets versions access latest', text)
            self.assertNotRegex(text, r'DRIVE_FOLDER_ID="\$\{DRIVE_FOLDER_ID:-[^}]+\}"')

    def test_agro_dataset_is_required_before_recurring_collector_deploy(self) -> None:
        deploy = Path("scripts/deploy_collectors_gcloud.sh").read_text(encoding="utf-8")
        preflight = Path("scripts/preflight_n6_gcp.sh").read_text(encoding="utf-8")
        self.assertIn('AGRO_DATASET="${AGRO_DATASET:-agro}"', deploy)
        self.assertIn('AGROLOG_AGRO_DATASET=${AGRO_DATASET}', deploy)
        self.assertIn('AGRO_DATASET="${AGRO_DATASET:-agro}"', preflight)

    def test_main_ruleset_requires_canonical_whole_project_gate(self) -> None:
        harden = Path("scripts/harden_github_repository.sh").read_text(encoding="utf-8")
        workflow = Path(".github/workflows/full-project-final-gate.yml").read_text(encoding="utf-8")
        self.assertIn('REQUIRED_CHECK="${REQUIRED_CHECK:-Whole project deterministic gate}"', harden)
        self.assertIn('name: Whole project deterministic gate', workflow)
        self.assertNotIn('REQUIRED_CHECK="${REQUIRED_CHECK:-unittest}"', harden)
        self.assertIn('strict_required_status_checks_policy', harden)
        self.assertIn('required_review_thread_resolution', harden)
        self.assertIn('"bypass_actors": []', harden)


if __name__ == "__main__":
    unittest.main()
