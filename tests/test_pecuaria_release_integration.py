from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class PecuariaReleaseIntegrationTests(unittest.TestCase):
    def test_full_release_routes_through_single_n6_homologation(self) -> None:
        gate = _text(".github/workflows/full-project-final-gate.yml")
        n6 = _text("scripts/homologate_n6_core.sh")
        self.assertIn("bash scripts/homologate_n6_core.sh", gate)
        self.assertIn("bash scripts/homologate_pecuaria_gcp.sh", n6)
        self.assertIn("PECUARIA_HOMOLOGATION_PASS", n6)
        self.assertIn("validate_pecuaria_trade_history.py", n6)
        self.assertIn("validate_pecuaria_gateway.py", n6)
        self.assertIn("pecuaria_registry_promotion=NOT_AUTOMATIC", n6)

    def test_livestock_workflow_is_diagnostic_only(self) -> None:
        workflow = _text(".github/workflows/pecuaria-production.yml")
        self.assertIn("name: pecuaria-live-probes", workflow)
        self.assertIn("Diagnostic LIVE probes only", workflow)
        self.assertNotIn("google-github-actions/auth@", workflow)
        self.assertNotIn("gcloud run", workflow)
        self.assertNotIn("homologate_pecuaria_gcp.sh", workflow)

    def test_collector_deploy_uses_registry_mode_and_preprovisioned_dataset(self) -> None:
        deploy = _text("scripts/deploy_collectors_gcloud.sh")
        self.assertIn('PECUARIA_DATASET="${PECUARIA_DATASET:-pecuaria}"', deploy)
        self.assertIn('require_dataset "$dataset"', deploy)
        self.assertIn('gcloud run jobs deploy "agrolog-pecuaria"', deploy)
        self.assertIn("AGROLOG_REGISTRY_MODE=1", deploy)
        self.assertIn("AGROLOG_DOMAIN=cattle", deploy)
        self.assertNotIn("bq --location=\"$BQ_LOCATION\" mk", deploy)

    def test_gateway_deploy_is_bounded_private_and_region_checked(self) -> None:
        deploy = _text("scripts/deploy_gateway_gcloud.sh")
        self.assertIn('PECUARIA_DATASET="${PECUARIA_DATASET:-pecuaria}"', deploy)
        self.assertIn('TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"', deploy)
        self.assertIn("actual=", deploy)
        self.assertIn('expected ${BQ_LOCATION}', deploy.replace("esperado", "expected"))
        self.assertIn("AGROLOG_BQ_MAX_BYTES_BILLED", deploy)
        self.assertIn("AGROLOG_BQ_QUERY_TIMEOUT_SECONDS", deploy)
        self.assertIn("assert_private_gateway", deploy)
        self.assertIn("AGROLOG_PECUARIA_DATASET", deploy)
        self.assertIn("AGROLOG_TRADE_DATASET", deploy)

    def test_gateway_image_contains_contract_and_composes_livestock_router(self) -> None:
        dockerfile = _text("gateway/Dockerfile")
        production_app = _text("gateway/production_app.py")
        self.assertIn("COPY --chown=agrolog:agrolog contracts /app/contracts", dockerfile)
        self.assertIn("gateway.production_app:app", dockerfile)
        self.assertIn("USER agrolog", dockerfile)
        self.assertIn("from .app import app", production_app)
        self.assertIn("pecuaria_router", production_app)
        self.assertIn("app.include_router(pecuaria_router)", production_app)


if __name__ == "__main__":
    unittest.main()
