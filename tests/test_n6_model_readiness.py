from __future__ import annotations

import json
import unittest
from pathlib import Path

from models.baselines import (
    climatology_probability,
    deterministic_balance,
    deterministic_export_parity,
    moving_average,
    next_linear_trend,
    seasonal_mean,
)
from models.readiness import evaluate_datamart, evaluate_model_contract


class BaselineTests(unittest.TestCase):
    def test_moving_average_and_linear_trend(self) -> None:
        self.assertEqual(moving_average([1, 2, 3, 4, 5], 5), 3)
        self.assertAlmostEqual(next_linear_trend([10, 12, 14, 16]), 18)

    def test_seasonal_mean(self) -> None:
        history = list(range(1, 13))
        self.assertEqual(seasonal_mean(history, seasonal_period=2, years=3), (11 + 9 + 7) / 3)

    def test_probability_and_deterministic_identities(self) -> None:
        self.assertEqual(climatology_probability([0, 1, 1, 0]), 0.5)
        self.assertEqual(deterministic_balance(opening_stock=10, production=100, crush=20, exports=60), 30)
        self.assertEqual(
            deterministic_export_parity(
                gross_export_value_brl_per_sc=150,
                port_cost_brl_per_sc=5,
                transport_brl_per_sc=20,
                commercial_cost_brl_per_sc=3,
            ),
            122,
        )


class ReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.datamart = json.loads(Path("contracts/soy_mt_datamart.v1.json").read_text(encoding="utf-8"))
        feature_contracts = json.loads(Path("models/feature_contracts.json").read_text(encoding="utf-8"))
        self.models = {item["model_id"]: item for item in feature_contracts["models"]}

    def test_datamart_blocks_materialization_when_required_source_missing(self) -> None:
        inventory = {
            "agro.conab_safra": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "history_seasons": 8},
            "logistica.armazens_conab": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "snapshots": 1},
            "referencia.municipios_ibge": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "snapshots": 1},
            "agro.imea_indicadores": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "history_seasons": 5},
            "clima.nasa_power_daily": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "history_years": 15},
        }
        result = evaluate_datamart(self.datamart, inventory)
        self.assertFalse(result.ready)
        self.assertTrue(any(f.code == "TABLE_MISSING" and "comex.comexstat_ncm_export" in f.message for f in result.failures))

    def test_datamart_passes_when_required_blocks_are_ready(self) -> None:
        inventory = {
            "agro.conab_safra": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "history_seasons": 8},
            "logistica.armazens_conab": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "snapshots": 1},
            "referencia.municipios_ibge": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "snapshots": 1},
            "agro.imea_indicadores": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "history_seasons": 5},
            "comex.comexstat_ncm_export": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": False, "history_years": 10},
            "clima.nasa_power_daily": {"exists": True, "qa_status": "pass", "point_in_time_ready": True, "canonical_geo_ready": True, "history_years": 15},
        }
        result = evaluate_datamart(self.datamart, inventory)
        self.assertTrue(result.ready, result.to_dict())

    def test_yield_model_refuses_short_history_and_missing_features(self) -> None:
        model = self.models["ALMT-SOY-YIELD-001"]
        result = evaluate_model_contract(
            model,
            available_metrics={"agro.produtividade", "clima.precipitacao", "clima.temperatura_media"},
            history_seasons=4,
            point_in_time_ready=True,
            baseline_ready=True,
        )
        self.assertFalse(result.ready)
        codes = {failure.code for failure in result.failures}
        self.assertIn("FEATURES_MISSING", codes)
        self.assertIn("INSUFFICIENT_HISTORY_SEASONS", codes)

    def test_yield_model_passes_only_with_features_history_pit_and_baseline(self) -> None:
        model = self.models["ALMT-SOY-YIELD-001"]
        result = evaluate_model_contract(
            model,
            available_metrics={"agro.produtividade", *model["features"]},
            history_seasons=10,
            point_in_time_ready=True,
            baseline_ready=True,
        )
        self.assertTrue(result.ready, result.to_dict())


if __name__ == "__main__":
    unittest.main()
