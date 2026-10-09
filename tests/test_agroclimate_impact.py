from __future__ import annotations

import unittest

from models.agroclimate_impact import AgroClimateContext, assess_agroclimate


class AgroClimateImpactTests(unittest.TestCase):
    def test_dry_sensitive_phase_produces_potential_risk_not_realized_loss(self) -> None:
        result = assess_agroclimate(AgroClimateContext(
            region="MT Norte", crop="soja", phase="florescimento",
            precipitation_percentile=12, days_without_rain=18,
            soil_water_percentile=15, forecast_precip_mm_7d=5,
        ))
        self.assertEqual(result.status, "READY")
        self.assertEqual(result.risk_level, "HIGH")
        self.assertEqual(result.evidence_class, "INFERIDO")
        self.assertTrue(any("potential" in item for item in result.potential_impacts))

    def test_missing_weather_fails_closed(self) -> None:
        result = assess_agroclimate(AgroClimateContext(region="MT", crop="milho", phase="vegetativo"))
        self.assertEqual(result.status, "DATA_GATED")
        self.assertEqual(result.risk_level, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
