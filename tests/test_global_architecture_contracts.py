from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GlobalArchitectureContractTests(unittest.TestCase):
    def read_json(self, path: str) -> dict:
        return json.loads((ROOT / path).read_text(encoding="utf-8"))

    def test_architecture_keeps_official_geographic_priority(self) -> None:
        text = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertIn("Mato Grosso → Brasil → América do Sul → Estados Unidos → Mundo", text)
        # Validate the canonical pipeline semantically instead of coupling the
        # contract to one prose rendering such as "fonte → collector → storage".
        for stage in ("1. fonte;", "2. collector;", "3. storage;", "4. normalização;", "5. validação;"):
            self.assertIn(stage, text)
        self.assertIn("UNTRUSTED EXTERNAL", text)

    def test_all_requested_intelligence_roles_are_canonical(self) -> None:
        payload = self.read_json("contracts/ai_roles.v1.json")
        names = {row["name"] for row in payload["roles"]}
        expected = {
            "AGROLOG CHIEF INTELLIGENCE AI",
            "CROP AI",
            "WEATHER AI",
            "GLOBAL MARKET AI",
            "BRAZIL MARKET AI",
            "US CROP AI",
            "ARGENTINA CROP AI",
            "LOGISTICS AI",
            "MARITIME AI",
            "HYDROLOGY AI",
            "ENERGY AI",
            "INDUSTRIAL AI",
            "CATTLE AI",
            "COMMERCIAL INTELLIGENCE AI",
            "NEWS IMPACT AI",
            "FORECAST AI",
            "REPORT EDITOR AI",
            "AUDITOR AI",
        }
        self.assertEqual(names, expected)
        self.assertEqual(len(payload["roles"]), 18)
        self.assertTrue(all(row["may_publish"] is False for row in payload["roles"]))

    def test_global_supply_demand_contract_has_full_balance_and_vintage(self) -> None:
        payload = self.read_json("contracts/global_supply_demand.v1.schema.json")
        required = set(payload["required"])
        for field in (
            "beginning_stocks", "production", "imports", "total_supply",
            "domestic_consumption", "processing", "exports", "ending_stocks",
            "stock_to_use", "marketing_year", "vintage_id", "data_publicacao",
        ):
            self.assertIn(field, required)

    def test_forecast_contract_preserves_point_in_time_cutoffs(self) -> None:
        payload = self.read_json("contracts/forecast_vintage.v1.schema.json")
        required = set(payload["required"])
        for field in ("issued_at", "training_cutoff", "feature_cutoff", "vintage_id", "model_version"):
            self.assertIn(field, required)
        self.assertEqual(payload["properties"]["evidence_class"]["const"], "projetado")
        self.assertEqual(
            set(payload["properties"]["forecast_type"]["enum"]),
            {"production", "yield", "weather", "price", "stocks", "exports", "freight", "eta", "congestion"},
        )

    def test_news_contract_distinguishes_correlation_from_causality(self) -> None:
        payload = self.read_json("contracts/news_signal.v0_5.schema.json")
        causal = set(payload["properties"]["causal_class"]["enum"])
        self.assertTrue({"CORRELATION", "CAUSAL_HYPOTHESIS", "SUPPORTED_CAUSALITY"}.issubset(causal))
        stages = set(payload["properties"]["causal_chain"]["items"]["properties"]["stage"]["enum"])
        self.assertEqual(stages, {"EVENT", "MECHANISM", "COMMODITY", "WORLD", "BRAZIL", "MATO_GROSSO"})

    def test_agent_evaluation_contract_fails_closed_on_security_and_grounding(self) -> None:
        payload = self.read_json("contracts/agent_evaluation.v1.schema.json")
        required = set(payload["required"])
        for field in (
            "agent_id", "scenario_id", "dataset_version", "prompt_version",
            "model_id", "run_id", "git_sha", "checks", "metrics",
            "overall_status", "data_coleta",
        ):
            self.assertIn(field, required)

        check_types = set(
            payload["properties"]["checks"]["items"]["properties"]["check_type"]["enum"]
        )
        for check in (
            "EVIDENCE_GROUNDING", "EPISTEMIC_CLASSIFICATION",
            "TOOL_AUTHORIZATION", "PROMPT_INJECTION",
            "DATA_EXFILTRATION", "TEMPORAL_CUTOFF",
        ):
            self.assertIn(check, check_types)

        self.assertEqual(
            set(payload["properties"]["overall_status"]["enum"]),
            {"PASS", "FAIL", "BLOCKED"},
        )

    def test_earth_observation_contract_preserves_asset_provenance_and_cutoff(self) -> None:
        payload = self.read_json("contracts/earth_observation_asset.v1.schema.json")
        required = set(payload["required"])
        for field in (
            "source_id", "provider", "discovery_method", "collection_id",
            "item_id", "asset_key", "asset_href", "acquisition_start",
            "acquisition_end", "data_referencia", "data_publicacao",
            "data_coleta", "geometry_ref", "bands", "license",
            "evidence_class", "source_url",
        ):
            self.assertIn(field, required)
        self.assertEqual(
            set(payload["properties"]["discovery_method"]["enum"]),
            {"STAC", "EARTHDATA_CMR", "OFFICIAL_API", "OFFICIAL_FILE"},
        )
        self.assertEqual(
            set(payload["properties"]["evidence_class"]["enum"]),
            {"observado", "estimado", "inferido"},
        )
        self.assertEqual(payload["properties"]["cloud_cover_pct"]["maximum"], 100)

    def test_phase0_audit_has_required_operational_dimensions(self) -> None:
        text = (ROOT / "docs" / "PHASE0_AUDIT_GAP_ANALYSIS_2026-09-14.md").read_text(encoding="utf-8")
        for token in ("Coleta", "Normalização", "Armazenamento", "Freshness", "Qualidade", "Análise", "Modelos", "Conhecimento", "Relatórios", "Alertas", "Testes"):
            self.assertIn(token, text)
        for domain in ("Estados Unidos", "Argentina", "Global", "Maritime", "Energia/diesel", "Gado"):
            self.assertIn(domain, text)


if __name__ == "__main__":
    unittest.main()
