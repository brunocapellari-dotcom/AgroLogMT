from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "harden_github_workflows.py"

spec = importlib.util.spec_from_file_location("harden_github_workflows", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkflowZizmorHardeningTests(unittest.TestCase):
    def test_fixture_gets_environment_and_checkout_credential_hardening(self) -> None:
        source = """name: demo\non:\n  workflow_dispatch:\npermissions:\n  contents: read\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    env:\n      PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}\n    steps:\n      - uses: actions/checkout@1111111111111111111111111111111111111111\n      - run: echo ok\n"""
        hardened = module.harden_text(source)
        self.assertIn("    environment: agrolog-production", hardened)
        self.assertIn("          persist-credentials: false", hardened)
        self.assertEqual(module.harden_text(hardened), hardened)

    def test_real_workflows_already_match_hardening_policy(self) -> None:
        offenders = []
        for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
            text = path.read_text(encoding="utf-8")
            if module.harden_text(text) != text:
                offenders.append(path.name)
        self.assertEqual(offenders, [], f"workflows ainda exigem hardening: {offenders}")


if __name__ == "__main__":
    unittest.main()
