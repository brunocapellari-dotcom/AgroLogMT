from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_ACTION = re.compile(r"^\s*-?\s*uses:\s*([^\s@]+)@([0-9a-f]{40})(?:\s+#.*)?$", re.MULTILINE)
ANY_REMOTE_ACTION = re.compile(r"^\s*-?\s*uses:\s*([^\s@./][^\s@]*)@([^\s#]+)", re.MULTILINE)


class SecurityPolicyTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_canonical_security_policy_defines_independent_confidentiality_classes(self) -> None:
        text = self.read("docs/SECURITY.md")
        for token in ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"):
            self.assertIn(f"`{token}`", text)
        self.assertIn("independente da classe de evidência", text)
        self.assertIn("Fail closed", text)

    def test_runtime_images_drop_root_before_entrypoint(self) -> None:
        collector = self.read("Dockerfile")
        gateway = self.read("gateway/Dockerfile")
        for text in (collector, gateway):
            self.assertIn("USER agrolog", text)
            self.assertNotIn("USER root", text)
        self.assertLess(collector.index("USER agrolog"), collector.index("ENTRYPOINT"))
        self.assertLess(gateway.index("USER agrolog"), gateway.index("CMD"))

    def test_wif_uses_immutable_github_ids_and_reconciles_existing_provider(self) -> None:
        text = self.read("scripts/setup_github_gcp_wif.sh")
        self.assertIn("assertion.repository_id", text)
        self.assertIn("assertion.repository_owner_id", text)
        self.assertIn("attribute.repository_id", text)
        self.assertIn("update-oidc", text)
        self.assertIn("refs/heads/main", text)
        self.assertNotIn("gh secret set ANA_IDENTIFICADOR", text)
        self.assertNotIn("gh secret set ANA_SENHA", text)

    def test_gateway_deploy_fails_closed_on_public_invoker_or_wrong_identity(self) -> None:
        text = self.read("scripts/deploy_gateway_gcloud.sh")
        self.assertIn("assert_private_gateway", text)
        self.assertIn("allUsers", text)
        self.assertIn("roles/run.invoker", text)
        self.assertIn("serviceAccountName", text)
        self.assertIn("GATEWAY_SERVICE_ACCOUNT", text)

    def test_p0_ci_never_receives_ana_production_credentials(self) -> None:
        text = self.read(".github/workflows/p0-connectors-ci.yml")
        self.assertNotIn("secrets.ANA_IDENTIFICADOR", text)
        self.assertNotIn("secrets.ANA_SENHA", text)
        self.assertNotIn("ANA_IDENTIFICADOR:", text)
        self.assertNotIn("ANA_SENHA:", text)

    def test_privileged_and_core_workflows_pin_remote_actions_by_full_sha(self) -> None:
        paths = (
            ".github/workflows/gcp-core-homologation.yml",
            ".github/workflows/maritime-ais-deploy.yml",
            ".github/workflows/maritime-ais-hourly.yml",
            ".github/workflows/p0-connectors-ci.yml",
            ".github/workflows/unit-tests.yml",
        )
        for path in paths:
            text = self.read(path)
            remote = list(ANY_REMOTE_ACTION.finditer(text))
            pinned = list(FULL_SHA_ACTION.finditer(text))
            self.assertTrue(remote, f"workflow sem actions remotas esperado: {path}")
            self.assertEqual(
                len(remote), len(pinned),
                f"toda action remota deve usar SHA completo em {path}",
            )

    def test_gitignore_and_dockerignore_cover_high_risk_secret_material(self) -> None:
        gitignore = self.read(".gitignore")
        dockerignore = self.read(".dockerignore")
        required = (
            ".env.*", "*.key", "*.pem", "*.p12", "*.pfx", ".npmrc", ".pypirc",
            "kubeconfig*", "*.tfstate", "credentials*.json", "service-account*.json",
        )
        for pattern in required:
            self.assertIn(pattern, gitignore)
            self.assertIn(pattern, dockerignore)

    def test_repository_does_not_contain_obvious_private_key_or_google_key_payload(self) -> None:
        ignored_dirs = {".git", ".venv", "venv", "node_modules", "dist", "outputs"}
        private_key = "-----BEGIN " + "PRIVATE KEY-----"
        rsa_private_key = "-----BEGIN RSA " + "PRIVATE KEY-----"
        google_private_key = '"private_key": "' + private_key
        signatures = (private_key, rsa_private_key, google_private_key)
        offenders: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(part in ignored_dirs for part in path.parts):
                continue
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".7z", ".xlsx", ".xls"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if any(signature in text for signature in signatures):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [], f"possível material de chave privada versionado: {offenders}")


if __name__ == "__main__":
    unittest.main()
