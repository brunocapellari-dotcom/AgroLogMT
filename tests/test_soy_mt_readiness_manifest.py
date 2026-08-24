from __future__ import annotations

import unittest

from scripts.build_soy_mt_readiness_manifest import build_manifest


class SoyMtReadinessManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = {
            "mart_id": "marts_soy_mt_v0_1",
            "blocks": [
                {"block_id": "production", "required_for_v1": True, "tables_all": ["agro.production"]},
                {"block_id": "climate", "required_for_v1": True, "tables_any": ["clima.a", "clima.b"]},
            ],
        }

    def test_source_readiness_does_not_fake_cloud_materialization(self) -> None:
        evidence = {
            "as_of": "2026-08-24T18:58:00-04:00",
            "cloud_authenticated": False,
            "blocks": {
                "production": {"source_ready": True, "source_state": "live", "local_qa_status": "pass", "point_in_time_evidence": True, "cloud_table_verified": False},
                "climate": {"source_ready": True, "source_state": "live_beta", "local_qa_status": "beta_pass", "point_in_time_evidence": False, "cloud_table_verified": False},
            },
            "model_targets": {"yield_realized": {"source_ready": True, "local_qa_status": "pass", "cloud_table_verified": False}},
        }
        manifest = build_manifest(self.contract, evidence)
        self.assertEqual(manifest["source_ready_blocks"], 2)
        self.assertEqual(manifest["strict_pit_source_ready_blocks"], 1)
        self.assertEqual(manifest["cloud_materialization_ready_blocks"], 0)
        self.assertFalse(manifest["materialization_allowed"])
        self.assertEqual(manifest["decision"], "BLOCK_CLOUD_MATERIALIZATION")

    def test_cloud_plan_can_only_open_when_required_tables_are_verified(self) -> None:
        evidence = {
            "as_of": "2026-08-24T18:58:00-04:00",
            "cloud_authenticated": True,
            "blocks": {
                "production": {"source_ready": True, "source_state": "live", "local_qa_status": "pass", "point_in_time_evidence": True, "cloud_table_verified": True},
                "climate": {"source_ready": True, "source_state": "live", "local_qa_status": "pass", "point_in_time_evidence": True, "cloud_table_verified": True},
            },
            "model_targets": {"yield_realized": {"source_ready": True, "local_qa_status": "pass", "cloud_table_verified": True}},
        }
        manifest = build_manifest(self.contract, evidence)
        self.assertTrue(manifest["materialization_allowed"])
        self.assertEqual(manifest["cloud_materialization_ready_blocks"], 2)


if __name__ == "__main__":
    unittest.main()
