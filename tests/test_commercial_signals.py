from __future__ import annotations

import unittest

from models.commercial_signals import (
    demand_30d_evidence_vector,
    producer_selling_conditions_vector,
)


class CommercialSignalsTests(unittest.TestCase):
    def test_producer_conditions_vector_never_invents_composite(self) -> None:
        result = producer_selling_conditions_vector(
            physical_price_percentile=81,
            basis_percentile=67,
            export_parity_spread_brl_sc=2.4,
            commercialization_delta_pp=-3.1,
        )
        self.assertEqual(result["status"], "VECTOR_READY")
        self.assertIsNone(result["composite_score"])
        self.assertIn("uncalibrated_composite_prohibited", result["flags"])

    def test_producer_conditions_fail_closed_when_component_missing(self) -> None:
        result = producer_selling_conditions_vector(
            physical_price_percentile=81,
            basis_percentile=None,
            export_parity_spread_brl_sc=2.4,
            commercialization_delta_pp=-3.1,
        )
        self.assertEqual(result["status"], "DATA_GATED")
        self.assertIn("basis_percentile", result["missing_components"])

    def test_percentile_range_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            producer_selling_conditions_vector(
                physical_price_percentile=101,
                basis_percentile=50,
                export_parity_spread_brl_sc=0,
                commercialization_delta_pp=0,
            )

    def test_demand_vector_keeps_programmed_and_realized_separate(self) -> None:
        result = demand_30d_evidence_vector(
            export_programmed_t=1_000_000,
            export_realized_trailing_30d_t=800_000,
            industrial_demand_reference_t=650_000,
            domestic_flow_trailing_30d_t=200_000,
        )
        self.assertEqual(result["status"], "VECTOR_READY")
        self.assertIsNone(result["aggregate_demand_t"])
        self.assertIsNone(result["forecast_30d_t"])
        self.assertEqual(result["components"]["export_programmed_t"], 1_000_000)
        self.assertEqual(result["components"]["export_realized_trailing_30d_t"], 800_000)
        self.assertIn("programmed_is_not_realized", result["flags"])

    def test_demand_vector_rejects_negative_volume(self) -> None:
        with self.assertRaises(ValueError):
            demand_30d_evidence_vector(
                export_programmed_t=-1,
                export_realized_trailing_30d_t=0,
                industrial_demand_reference_t=0,
                domestic_flow_trailing_30d_t=0,
            )


if __name__ == "__main__":
    unittest.main()
