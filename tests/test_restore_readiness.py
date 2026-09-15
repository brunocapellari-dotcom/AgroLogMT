from __future__ import annotations

import unittest

from models.restore_readiness import assert_restore_verified, evaluate_restore_drill


class RestoreReadinessTests(unittest.TestCase):
    def fixture(self) -> dict:
        return {
            "version": "1.0.0",
            "drill_id": "restore-20260915-fixture",
            "environment": "staging",
            "started_at": "2026-09-15T12:00:00Z",
            "finished_at": "2026-09-15T12:20:00Z",
            "backup_type": "BIGQUERY_SNAPSHOT",
            "source_ref": "bigquery://fixture/source",
            "restore_target": "bigquery://fixture/restore",
            "status": "PASS",
            "rpo_minutes": 60,
            "rto_minutes": 30,
            "validation": {
                "object_count": "NOT_APPLICABLE",
                "row_count": "PASS",
                "hash_or_checksum": "PASS",
                "permissions": "PASS",
                "secrets_not_exported": True,
            },
            "evidence": ["evidence://restore/drill"],
        }

    def test_verified_restore_requires_evidence_and_validation(self) -> None:
        result = assert_restore_verified(self.fixture())
        self.assertTrue(result.verified)

    def test_backup_without_successful_restore_is_not_verified(self) -> None:
        payload = self.fixture()
        payload["status"] = "PLANNED"
        payload["finished_at"] = None
        result = evaluate_restore_drill(payload)
        self.assertFalse(result.verified)
        self.assertIn("status_not_pass", result.blocking_reasons)
        self.assertIn("missing_finished_at", result.blocking_reasons)

    def test_permission_failure_blocks_restore_gate(self) -> None:
        payload = self.fixture()
        payload["validation"]["permissions"] = "FAIL"
        with self.assertRaises(RuntimeError):
            assert_restore_verified(payload)

    def test_secret_export_risk_blocks_restore_gate(self) -> None:
        payload = self.fixture()
        payload["validation"]["secrets_not_exported"] = False
        result = evaluate_restore_drill(payload)
        self.assertIn("secrets_export_risk", result.blocking_reasons)


if __name__ == "__main__":
    unittest.main()
