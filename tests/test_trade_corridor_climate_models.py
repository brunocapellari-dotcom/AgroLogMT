from __future__ import annotations

import unittest
from pathlib import Path

from models.agroclimate_events import classify_precipitation_percentile, precipitation_anomaly_pct
from models.logistics_corridors import CorridorObservation, aggregate_corridors, multimodal_cost_brl_per_t
from models.trade_codes import codes_for_products, load_trade_code_sets, product_for_ncm


ROOT = Path(__file__).resolve().parents[1]


class TradeCodesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mapping = load_trade_code_sets(ROOT / "contracts/product_trade_codes.v1.json")

    def test_soy_corn_cotton_and_fertilizers_are_mapped(self) -> None:
        for product_id in (
            "soja_grao",
            "milho_grao",
            "algodao_bruto",
            "fertilizante_ureia",
            "fertilizante_cloreto_potassio",
            "fertilizante_map",
        ):
            self.assertIn(product_id, self.mapping)

    def test_temporal_candidate_codes_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            codes_for_products(self.mapping, ["fertilizante_dap_catalog_candidates"])

    def test_no_silent_double_counting(self) -> None:
        codes = codes_for_products(self.mapping, ["soja_grao", "milho_grao"])
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(product_for_ncm(self.mapping, "10059010"), "milho_grao")


class CorridorTests(unittest.TestCase):
    def test_route_type_is_explicit_not_inferred(self) -> None:
        row = CorridorObservation("A-B", "A", "B", "UNKNOWN", "ROAD", product_id="soja")
        self.assertEqual(row.route_type, "UNKNOWN")

    def test_aggregate_preserves_export_and_domestic_separately(self) -> None:
        rows = [
            CorridorObservation("A-B", "A", "B", "EXPORT", "ROAD", "soja", 100, 150, 0.2),
            CorridorObservation("A-B", "A", "B", "EXPORT", "RAIL", "soja", 200, 120, 0.1),
            CorridorObservation("A-B", "A", "B", "DOMESTIC", "ROAD", "soja", 50, 140, 0.18),
        ]
        result = aggregate_corridors(rows)
        self.assertEqual(len(result), 2)
        export = next(row for row in result if row["route_type"] == "EXPORT")
        self.assertEqual(export["volume_t_sum"], 300.0)
        self.assertEqual(export["modes"], ["RAIL", "ROAD"])

    def test_multimodal_cost(self) -> None:
        self.assertEqual(multimodal_cost_brl_per_t(120, 20, 35), 175.0)


class AgroClimateEventsTests(unittest.TestCase):
    def test_anomaly_and_extreme_classification(self) -> None:
        anomaly = precipitation_anomaly_pct(40, 100)
        self.assertEqual(anomaly, -60.0)
        event = classify_precipitation_percentile(3, anomaly_pct=anomaly)
        self.assertEqual(event.event_type, "DRY_EXTREME")
        self.assertEqual(event.evidence_class, "DERIVADO_DE_OBSERVADO")


if __name__ == "__main__":
    unittest.main()
