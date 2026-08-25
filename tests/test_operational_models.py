import unittest

from models.operational_models import (
    ModelGate,
    absorption_scenarios,
    freight_pressure_label,
    hhi,
    hydro_percentile_risk,
    m04_class,
    m04_score,
    percentile_rank,
    ramp_adjusted_activity_score,
    regime_shift,
)


class OperationalModelsTest(unittest.TestCase):
    def test_percentile_rank(self):
        self.assertAlmostEqual(percentile_rank([1, 2, 3, 4], 3), 62.5)

    def test_hhi(self):
        self.assertAlmostEqual(hhi([50, 50]), 0.5)
        self.assertAlmostEqual(hhi([100]), 1.0)

    def test_regime_shift(self):
        self.assertTrue(regime_shift(previous_hhi=.20, current_hhi=.31, previous_top_share=40, current_top_share=42, leader_changed=False))
        self.assertTrue(regime_shift(previous_hhi=.20, current_hhi=.21, previous_top_share=40, current_top_share=41, leader_changed=True))
        self.assertFalse(regime_shift(previous_hhi=.20, current_hhi=.21, previous_top_share=40, current_top_share=41, leader_changed=False))

    def test_freight_pressure(self):
        self.assertEqual(freight_pressure_label([90, 91, 92, 60])["label"], "ELEVATED")
        self.assertEqual(freight_pressure_label([95, 96, 94, 90])["label"], "HIGH")

    def test_ramp_activity(self):
        score = ramp_adjusted_activity_score(yoy_growth_pct=17.7, utilization_pct=52.7, capacity_step_pct=7.0, months_since_step=1)
        self.assertGreater(score, 70)

    def test_absorption(self):
        s = absorption_scenarios(1000, operating_days=30)
        self.assertEqual(s["base_t"], 24000)
        self.assertLess(s["low_t"], s["base_t"])
        self.assertGreater(s["high_t"], s["base_t"])

    def test_hydro(self):
        self.assertEqual(hydro_percentile_risk(30), 0)
        self.assertEqual(hydro_percentile_risk(0.5), 100)
        score = m04_score(100, 100, 100, 100, 100)
        self.assertEqual(score, 100)
        self.assertEqual(m04_class(score), "CRITICAL")

    def test_gate(self):
        self.assertEqual(ModelGate("M01", concept=True, data=True).highest_gate, "DATA")


if __name__ == "__main__":
    unittest.main()
