from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml


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

    def test_dependabot_uses_at_least_seven_day_cooldown_for_all_ecosystems(self) -> None:
        path = ROOT / ".github" / "dependabot.yml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        updates = config.get("updates", [])
        self.assertTrue(updates, "dependabot.yml precisa declarar updates")
        offenders = []
        for item in updates:
            days = (item.get("cooldown") or {}).get("default-days", 0)
            if not isinstance(days, int) or days < 7:
                offenders.append(f"{item.get('package-ecosystem')}:{item.get('directory')}={days}")
        self.assertEqual(offenders, [], f"cooldown Dependabot abaixo de 7 dias: {offenders}")


if __name__ == "__main__":
    unittest.main()
