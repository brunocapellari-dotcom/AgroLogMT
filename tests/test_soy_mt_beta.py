from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from scripts.generate_soy_mt_beta import _aggregate_climate, evenly_spaced, render_markdown


class SoyMtBetaTests(unittest.TestCase):
    def test_evenly_spaced_is_deterministic_and_covers_edges(self) -> None:
        values = list(range(10))
        sampled = evenly_spaced(values, 4)
        self.assertEqual(sampled[0], 0)
        self.assertEqual(sampled[-1], 9)
        self.assertEqual(len(sampled), 4)
        self.assertEqual(sampled, evenly_spaced(values, 4))

    def test_climate_aggregation_separates_two_seven_day_windows(self) -> None:
        rows = []
        for day in range(1, 15):
            when = date(2026, 8, day).isoformat()
            rain = 1.0 if day <= 7 else 2.0
            rows.extend([
                SimpleNamespace(date=when, parameter="PRECTOTCORR", value=rain),
                SimpleNamespace(date=when, parameter="T2M", value=25.0),
                SimpleNamespace(date=when, parameter="T2M_MAX", value=31.0),
                SimpleNamespace(date=when, parameter="T2M_MIN", value=19.0),
                SimpleNamespace(date=when, parameter="RH2M", value=60.0),
            ])
        result = _aggregate_climate([rows], cutoff=date(2026, 8, 14))
        self.assertEqual(result["rain_7d_mean_mm"], 14.0)
        self.assertEqual(result["rain_previous_7d_mean_mm"], 7.0)
        self.assertEqual(result["rain_change_pct"], 100.0)
        self.assertEqual(result["temperature_mean_c"], 25.0)

    def test_markdown_labels_beta_and_storage_semantics(self) -> None:
        snapshot = {
            "generated_at_local": "2026-08-24T16:00:00-03:00",
            "status": "ok",
            "available_blocks": 3,
            "total_blocks": 3,
            "blocks": {
                "production": {
                    "status": "ok", "safra": "2025/26", "area_mil_ha": 13006.2,
                    "produtividade_kg_ha": 3969.0, "producao_mil_t": 51621.6,
                    "producao_var_pct": 2.0, "data_publicacao": "2026-08-13T12:00:00+00:00",
                },
                "storage": {
                    "status": "ok", "warehouse_records_mt": 100, "municipalities_mt": 50,
                    "capacidade_estatica_mt_t": 1000000.0, "records_with_quality_flags": 0,
                },
                "climate": {
                    "status": "ok", "sample_count": 7, "grid_points_total": 132,
                    "rain_7d_mean_mm": 10.0, "rain_previous_7d_mean_mm": 5.0,
                    "rain_change_pct": 100.0, "temperature_mean_c": 25.0,
                    "temperature_max_daily_mean_c": 31.0, "relative_humidity_mean_pct": 60.0,
                },
            },
            "limitations": ["teste"],
        }
        markdown = render_markdown(snapshot)
        self.assertIn("Soja MT Beta", markdown)
        self.assertIn("não representa capacidade livre", markdown)
        self.assertIn("research_only", markdown)


if __name__ == "__main__":
    unittest.main()
