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
        self.assertIn("fonte → collector → storage", text)
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

    def test_phase0_audit_has_required_operational_dimensions(self) -> None:
        text = (ROOT / "docs" / "PHASE0_AUDIT_GAP_ANALYSIS_2026-09-14.md").read_text(encoding="utf-8")
        for token in ("Coleta", "Normalização", "Armazenamento", "Freshness", "Qualidade", "Análise", "Modelos", "Conhecimento", "Relatórios", "Alertas", "Testes"):
            self.assertIn(token, text)
        for domain in ("Estados Unidos", "Argentina", "Global", "Maritime", "Energia/diesel", "Gado"):
            self.assertIn(domain, text)


if __name__ == "__main__":
    unittest.main()
