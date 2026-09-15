from __future__ import annotations

import unittest

from collector.source_promotion import assert_source_promotable, evaluate_source_promotion


CHECKS = (
    "source", "collector", "storage", "normalization", "validation", "analysis",
    "knowledge", "report_or_alert", "tests", "freshness", "security", "lineage",
    "observability", "backup_restore",
)


def gate_payload(status: str = "PASS", *, target_state: str = "PRODUCTION") -> dict:
    checks = {
        name: {"status": status, "evidence": [f"evidence://{name}"] if status == "PASS" else []}
        for name in CHECKS
    }
    return {
        "version": "1.0.0",
        "source_id": "fixture_source",
        "target_state": target_state,
        "checks": checks,
    }


class SourcePromotionTests(unittest.TestCase):
    def test_production_requires_all_checks_pass(self) -> None:
        evaluation = assert_source_promotable(gate_payload())
        self.assertTrue(evaluation.ready)
        self.assertEqual(evaluation.blocking_checks, ())

    def test_missing_check_blocks_promotion(self) -> None:
        payload = gate_payload()
        payload["checks"]["freshness"] = {"status": "MISSING", "evidence": []}
        evaluation = evaluate_source_promotion(payload)
        self.assertFalse(evaluation.ready)
        self.assertIn("freshness", evaluation.blocking_checks)
        with self.assertRaises(RuntimeError):
            assert_source_promotable(payload)

    def test_pass_without_evidence_fails_closed(self) -> None:
        payload = gate_payload()
        payload["checks"]["security"] = {"status": "PASS", "evidence": []}
        with self.assertRaisesRegex(ValueError, "PASS requires evidence"):
            evaluate_source_promotion(payload)

    def test_not_applicable_blocks_production(self) -> None:
        payload = gate_payload()
        payload["checks"]["backup_restore"] = {
            "status": "NOT_APPLICABLE",
            "evidence": [],
            "rationale": "fixture only",
        }
        evaluation = evaluate_source_promotion(payload)
        self.assertFalse(evaluation.ready)
        self.assertIn("backup_restore", evaluation.blocking_checks)

    def test_not_applicable_can_be_warning_in_shadow(self) -> None:
        payload = gate_payload(target_state="SHADOW")
        payload["checks"]["backup_restore"] = {
            "status": "NOT_APPLICABLE",
            "evidence": [],
            "rationale": "restore gate enters before production",
        }
        evaluation = evaluate_source_promotion(payload)
        self.assertTrue(evaluation.ready)
        self.assertTrue(evaluation.warnings)


if __name__ == "__main__":
    unittest.main()
