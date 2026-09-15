from __future__ import annotations

import re
import unittest
from pathlib import Path


class SecurityPolicyTests(unittest.TestCase):
    def test_gateway_container_runs_non_root(self) -> None:
        dockerfile = Path("gateway/Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(dockerfile, r"(?m)^USER\s+(?!root\b)\S+")
        self.assertIn("--no-server-header", dockerfile)
        self.assertIn("--no-date-header", dockerfile)

    def test_gateway_deploy_refuses_public_invoker_and_bounds_resources(self) -> None:
        script = Path("scripts/deploy_gateway_gcloud.sh").read_text(encoding="utf-8")
        self.assertNotIn("--allow-unauthenticated", script)
        self.assertIn("roles/run.invoker", script)
        self.assertIn("allUsers", script)
        self.assertIn("--max-instances", script)
        self.assertIn("--concurrency", script)
        self.assertIn("AGROLOG_BQ_MAX_BYTES_BILLED", script)
        self.assertIn("AGROLOG_ENABLE_DOCS=0", script)

    def test_gateway_has_query_cost_timeout_and_security_headers(self) -> None:
        app = Path("gateway/app.py").read_text(encoding="utf-8")
        self.assertIn("maximum_bytes_billed=BQ_MAX_BYTES_BILLED", app)
        self.assertIn("result(timeout=BQ_QUERY_TIMEOUT_SECONDS)", app)
        for header in (
            "x-content-type-options",
            "x-frame-options",
            "content-security-policy",
            "referrer-policy",
            "permissions-policy",
        ):
            self.assertIn(header, app)
        self.assertIn('ENABLE_DOCS = os.environ.get("AGROLOG_ENABLE_DOCS", "0") == "1"', app)
        self.assertIn("CORS wildcard é proibido", app)

    def test_ais_runtime_requires_explicit_geofence_validation(self) -> None:
        script = Path("scripts/deploy_ais_worker_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('GEOFENCE_VALIDATED="${GEOFENCE_VALIDATED:-0}"', script)
        self.assertIn("geofences operacionais fornecidas sem GEOFENCE_VALIDATED=1", script)
        self.assertIn("--parallelism 1", script)
        self.assertIn("--tasks 1", script)
        self.assertIn("AISSTREAM_API_KEY=${SECRET_NAME}:latest", script)

    def test_wif_bootstrap_prohibits_unprotected_main_and_sa_keys(self) -> None:
        script = Path("scripts/setup_github_gcp_wif.sh").read_text(encoding="utf-8")
        self.assertIn('ALLOW_UNPROTECTED_MAIN="${ALLOW_UNPROTECTED_MAIN:-0}"', script)
        self.assertIn('ALLOW_USER_MANAGED_SA_KEYS="${ALLOW_USER_MANAGED_SA_KEYS:-0}"', script)
        self.assertIn("branches/main", script)
        self.assertIn("keyType=USER_MANAGED", script)
        self.assertIn("--public-access-prevention=enforced", script)
        self.assertNotRegex(script, re.compile(r"service-accounts\s+keys\s+create"))
        self.assertIn("assertion.ref=='refs/heads/main'", script)

    def test_security_gate_has_read_only_permissions_and_pinned_actions(self) -> None:
        workflow = Path(".github/workflows/security-gate.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertNotIn("write-all", workflow.lower())
        self.assertIn("pip-audit", workflow)
        self.assertIn("bandit", workflow)
        self.assertIn("npm audit", workflow)
        uses = re.findall(r"uses:\s*([^\s]+)", workflow)
        self.assertTrue(uses)
        for ref in uses:
            self.assertRegex(ref, r"@[0-9a-f]{40}$", msg=f"un-pinned action: {ref}")

    def test_secret_files_are_ignored(self) -> None:
        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        for item in (".env", "*.key", "*.pem", "credentials*.json", "service-account*.json"):
            self.assertIn(item, gitignore)


if __name__ == "__main__":
    unittest.main()
