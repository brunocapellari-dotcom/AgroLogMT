from __future__ import annotations

import unittest
from datetime import datetime, timezone

from collector.agroclimate import normalize_daily_observation
from collector.biomass import classify_biomass_evidence, normalize_biomass_observation
from collector.freight_observations import normalize_offer


UTC = timezone.utc


class OperationalNormalizationTests(unittest.TestCase):
    def test_climate_preserves_missingness_and_flags_inconsistent_temperature(self) -> None:
        row = normalize_daily_observation(
            source_id="inmet_weather",
            geo_id="5105259",
            reference_date="2026-09-29",
            collected_at=datetime(2026, 9, 29, 12, tzinfo=UTC),
            precipitation_mm=None,
            tmin_c=30,
            tmax_c=25,
        )
        self.assertIn("precipitation_missing", row.quality_flags)
        self.assertIn("tmin_gt_tmax", row.quality_flags)
        self.assertEqual(row.competencia, "2026-09")

    def test_freight_offer_never_promotes_offer_to_executed(self) -> None:
        row = normalize_offer(
            source_channel_type="whatsapp",
            source_provider="authorized_adapter",
            source_channel_id_hash="abc",
            source_message_id_hash="def",
            published_at="2026-09-29T10:00:00+00:00",
            collected_at="2026-09-29T10:01:00+00:00",
            origin_municipality_id="5107909",
            destination_municipality_id="5107602",
            product_id="soja",
            freight_value_numeric=180,
            freight_unit_id="R$/t",
            distance_km=900,
            payload_t=37,
        )
        self.assertEqual(row.evidence_class, "OBSERVADO")
        self.assertEqual(row.executed_status, "DESCONHECIDO")
        self.assertFalse(row.requires_review)
        self.assertAlmostEqual(row.freight_brl_per_t_km or 0, 0.2)

    def test_ambiguous_freight_unit_requires_review(self) -> None:
        row = normalize_offer(
            source_channel_type="whatsapp",
            source_provider="authorized_adapter",
            source_channel_id_hash="abc",
            source_message_id_hash="xyz",
            published_at="2026-09-29T10:00:00+00:00",
            collected_at="2026-09-29T10:01:00+00:00",
            origin_municipality_id=None,
            destination_municipality_id=None,
            product_id=None,
            freight_value_numeric=5000,
            freight_unit_id="por carga",
            normalization_confidence=0.6,
        )
        self.assertTrue(row.requires_review)
        self.assertIsNone(row.freight_brl_per_t)

    def test_biomass_coefficient_is_estimate(self) -> None:
        evidence, semantics = classify_biomass_evidence(
            metric_id="residue_potential_t",
            derivation="agricultural_volume_x_residue_coefficient",
        )
        self.assertEqual(evidence, "ESTIMADO")
        self.assertEqual(semantics, "ESTIMATIVA_POR_COEFICIENTE")

    def test_industrial_consumption_requires_direct_basis(self) -> None:
        with self.assertRaises(ValueError):
            normalize_biomass_observation(
                source_id="x",
                geo_id="MT",
                biomass_type="lenha",
                metric_id="industrial_consumption_t",
                value=100,
                unit="t",
                reference_date="2026-09-01",
                collected_at="2026-09-29T10:00:00+00:00",
                derivation="inferred_from_generation",
            )


if __name__ == "__main__":
    unittest.main()
