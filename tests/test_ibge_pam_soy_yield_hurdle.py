from __future__ import annotations

import unittest

from scripts.build_ibge_pam_soy_yield_hurdle import (
    YieldObservation,
    lagged_hurdle,
    linear_trend_at_horizon,
    parse_sidra_rows,
)


class IbgePamSoyYieldHurdleTests(unittest.TestCase):
    def test_parse_sidra_rows_filters_mt_soy_yield(self) -> None:
        payload = [
            {"D1N": "Unidade da Federação", "D2N": "Variável", "D3N": "Ano", "D4N": "Produto", "V": "Valor"},
            {"D1N": "Mato Grosso", "D2N": "Rendimento médio da produção", "D3N": "2022", "D4N": "Soja (em grão)", "V": "3500"},
            {"D1N": "Mato Grosso", "D2N": "Rendimento médio da produção", "D3N": "2023", "D4N": "Soja (em grão)", "V": "3.750"},
            {"D1N": "Goiás", "D2N": "Rendimento médio da produção", "D3N": "2023", "D4N": "Soja (em grão)", "V": "3900"},
        ]
        rows = parse_sidra_rows(payload)
        self.assertEqual([row.year for row in rows], [2022, 2023])
        self.assertEqual(rows[0].yield_kg_ha, 3500.0)

    def test_linear_trend_horizon_projects_requested_steps(self) -> None:
        self.assertAlmostEqual(linear_trend_at_horizon([100.0, 110.0, 120.0], 2), 140.0)

    def test_lagged_hurdle_never_uses_target_or_previous_year_label_with_lag_two(self) -> None:
        observations = [
            YieldObservation(year=2000 + idx, yield_kg_ha=3000.0 + idx * 10.0, geo="Mato Grosso", variable="Rendimento", product="Soja")
            for idx in range(12)
        ]
        result = lagged_hurdle(observations, label_lag_years=2, min_train=5)
        self.assertTrue(result["folds"])
        for fold in result["folds"]:
            self.assertEqual(fold["last_available_year"], fold["target_year"] - 2)
        self.assertEqual(result["status"], "research_only")


if __name__ == "__main__":
    unittest.main()
