from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.radar_poc_suite import crawl4ai_poc
from experiments.radar_poc_suite import langgraph_poc
from experiments.radar_poc_suite import ollama_poc
from experiments.radar_poc_suite import polymarket_poc
from experiments.radar_poc_suite.librechat import mock_gateway

ROOT = Path(__file__).resolve().parents[1]


class CrawlSafetyTests(unittest.TestCase):
    def test_rejects_localhost(self):
        with self.assertRaises(ValueError):
            crawl4ai_poc.validate_public_url("http://localhost/admin")

    def test_rejects_private_literal_ip(self):
        with self.assertRaises(ValueError):
            crawl4ai_poc.validate_public_url("http://10.0.0.1/data")

    def test_accepts_public_https_domain(self):
        self.assertEqual(
            crawl4ai_poc.validate_public_url("https://example.com/data"),
            "https://example.com/data",
        )


class PolymarketSafetyTests(unittest.TestCase):
    def test_accepts_only_polymarket_public_url(self):
        self.assertEqual(
            polymarket_poc.validate_market_url("https://polymarket.com/event/example"),
            "https://polymarket.com/event/example",
        )
        with self.assertRaises(ValueError):
            polymarket_poc.validate_market_url("https://example.com/event/example")

    def test_source_contains_no_authenticated_trading_primitives(self):
        source = (ROOT / "polymarket_poc.py").read_text(encoding="utf-8")
        forbidden = [
            "ApiCreds",
            "PRIVATE_KEY",
            "create_and_post_order",
            "create_and_post_market_order",
            "CLOB_SECRET",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


class LocalOnlyTests(unittest.TestCase):
    def test_ollama_is_localhost_only(self):
        self.assertEqual(ollama_poc.BASE_URL, "http://127.0.0.1:11434")

    def test_mock_gateway_is_localhost_only(self):
        self.assertEqual(mock_gateway.HOST, "127.0.0.1")

    def test_code_server_example_is_localhost_only(self):
        config = (ROOT / "code_server" / "config.yaml.example").read_text(encoding="utf-8")
        self.assertIn("bind-addr: 127.0.0.1:8080", config)
        self.assertNotIn("bind-addr: 0.0.0.0", config)


class AgentGovernanceTests(unittest.TestCase):
    def test_auditor_blocks_missing_evidence(self):
        result = langgraph_poc.auditor_node({"question": "teste"})
        self.assertEqual(result["audit_status"], "BLOCKED_NO_EVIDENCE")

    def test_auditor_allows_with_limitations_when_evidence_exists(self):
        result = langgraph_poc.auditor_node(
            {"question": "teste", "evidence": ["fixture_sintetico"]}
        )
        self.assertEqual(result["audit_status"], "PASS_WITH_LIMITATIONS")


class PublicationGovernanceTests(unittest.TestCase):
    def test_hyperframes_fixture_cannot_recalculate_or_change_conclusion(self):
        payload = json.loads(
            (ROOT / "hyperframes" / "approved_report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(payload["fixture"])
        self.assertTrue(payload["approved_for_render"])
        self.assertFalse(payload["governance"]["may_recalculate_indicators"])
        self.assertFalse(payload["governance"]["may_change_conclusions"])
        self.assertTrue(
            payload["governance"]["human_review_required_before_external_publication"]
        )


class QuantGovernanceTests(unittest.TestCase):
    def test_vectorbt_poc_has_explicit_point_in_time_shift(self):
        source = (ROOT / "vectorbt_poc.py").read_text(encoding="utf-8")
        self.assertIn("shift(1)", source)
        self.assertIn("future only used as evaluation target", source)


class ManifestTests(unittest.TestCase):
    def test_suite_manifest_forbids_production_and_real_credentials(self):
        payload = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(payload["production_authorized"])
        self.assertFalse(payload["bigquery_write_allowed"])
        self.assertFalse(payload["real_credentials_allowed"])
        self.assertEqual(len(payload["components"]), 9)


if __name__ == "__main__":
    unittest.main()
