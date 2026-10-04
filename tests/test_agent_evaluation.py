from __future__ import annotations

import unittest

from models.agent_evaluation import evaluate_agent_evaluation


def _payload(*, evidence_required: bool = True) -> dict:
    check_types = [
        "OUTPUT_SCHEMA",
        "EPISTEMIC_CLASSIFICATION",
        "TOOL_AUTHORIZATION",
        "PROMPT_INJECTION",
        "DATA_EXFILTRATION",
        "TEMPORAL_CUTOFF",
    ]
    if evidence_required:
        check_types += ["EVIDENCE_GROUNDING", "CITATION_TRACEABILITY"]
    return {
        "checks": [{"check_type": name, "status": "PASS"} for name in check_types],
        "evidence_required": evidence_required,
        "evidence_coverage": 1.0 if evidence_required else None,
        "tool_calls": [
            {"tool_name": "agrolog_gateway.read", "authorized": True, "status": "PASS"}
        ],
        "overall_status": "PASS",
    }


class AgentEvaluationTests(unittest.TestCase):
    def test_complete_grounded_evaluation_passes(self) -> None:
        decision = evaluate_agent_evaluation(_payload())
        self.assertEqual(decision.status, "PASS")
        self.assertEqual(decision.reasons, ())

    def test_missing_security_check_blocks(self) -> None:
        payload = _payload()
        payload["checks"] = [
            row for row in payload["checks"] if row["check_type"] != "PROMPT_INJECTION"
        ]
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "BLOCKED")
        self.assertIn("missing_check:PROMPT_INJECTION", decision.reasons)

    def test_failed_security_check_fails(self) -> None:
        payload = _payload()
        next(
            row for row in payload["checks"] if row["check_type"] == "DATA_EXFILTRATION"
        )["status"] = "FAIL"
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "FAIL")
        self.assertIn("failed_check:DATA_EXFILTRATION", decision.reasons)

    def test_unauthorized_tool_fails(self) -> None:
        payload = _payload()
        payload["tool_calls"].append(
            {"tool_name": "bigquery.direct_write", "authorized": False, "status": "FAIL"}
        )
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "FAIL")
        self.assertIn("unauthorized_tool:bigquery.direct_write", decision.reasons)

    def test_incomplete_evidence_fails_when_grounding_is_required(self) -> None:
        payload = _payload()
        payload["evidence_coverage"] = 0.99
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "FAIL")
        self.assertTrue(
            any(reason.startswith("evidence_coverage_below_1:") for reason in decision.reasons)
        )

    def test_evidence_checks_are_not_required_for_non_evidence_scenario(self) -> None:
        payload = _payload(evidence_required=False)
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "PASS")

    def test_external_evaluator_cannot_declare_fail_as_pass(self) -> None:
        payload = _payload()
        payload["overall_status"] = "FAIL"
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "BLOCKED")
        self.assertIn("declared_status_not_pass:FAIL", decision.reasons)

    def test_duplicate_check_blocks_ambiguous_evidence(self) -> None:
        payload = _payload()
        payload["checks"].append({"check_type": "OUTPUT_SCHEMA", "status": "PASS"})
        decision = evaluate_agent_evaluation(payload)
        self.assertEqual(decision.status, "BLOCKED")
        self.assertIn("duplicate_check:OUTPUT_SCHEMA", decision.reasons)


if __name__ == "__main__":
    unittest.main()
