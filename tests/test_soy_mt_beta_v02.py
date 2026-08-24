from __future__ import annotations

import unittest
from datetime import date
from types import SimpleNamespace

from scripts.generate_soy_mt_beta_v02 import _revision_line, _safe_pct_change, aggregate_agroclimate, render_markdown


def row(day: str, parameter: str, value: float):
    return SimpleNamespace(date=day, parameter=parameter, value=value)


def point_rows(start_day: int = 1) -> list[SimpleNamespace]:
    rows: list[SimpleNamespace] = []
    for day in range(start_day, start_day + 14):
        iso = f"2026-08-{day:02d}"
        rows.extend([
            row(iso, "PRECTOTCORR", 2.0 if day <= 7 else 0.5),
            row(iso, "T2M", 27.0),
            row(iso, "T2M_MAX", 34.0),
            row(iso, "T2M_MIN", 20.0),
            row(iso, "RH2M", 50.0),
        ])
    return rows


class SoyBetaV02Tests(unittest.TestCase):
    def test_safe_pct_change(self) -> None:
        self.assertAlmostEqual(_safe_pct_change(110.0, 100.0), 10.0)
        self.assertIsNone(_safe_pct_change(10.0, 0.0))
        self.assertIsNone(_safe_pct_change(None, 10.0))

    def test_agroclimate_aggregates_eto_gdd_and_gap(self) -> None:
        rows = [point_rows(), point_rows()]
        result = aggregate_agroclimate(rows, latitudes=[-13.0, -15.0], cutoff=date(2026, 8, 14))
        self.assertEqual(result["period_last_7d"], ["2026-08-08", "2026-08-14"])
        self.assertAlmostEqual(result["rain_7d_mean_mm"], 3.5, places=1)
        self.assertGreater(result["eto_hargreaves_7d_mean_mm"], 0.0)
        self.assertGreater(result["gdd_base10_7d_mean"], 0.0)
        self.assertLess(result["rain_minus_eto_7d_mean_mm"], 0.0)
        self.assertEqual(result["climatic_water_gap_signal"], "demanda_atmosferica_acima_da_chuva")
        self.assertEqual(result["signal_evidence_class"], "inferido")

    def test_revision_line_is_explicit(self) -> None:
        production = {
            "revision_vs_previous_levantamento": {
                "previous_levantamento": 10,
                "producao_revision_mil_t": 250.0,
                "producao_revision_pct": 0.5,
            }
        }
        text = _revision_line(production)
        self.assertIn("alta", text)
        self.assertIn("250,0", text)
        self.assertIn("10o levantamento", text)

    def test_markdown_preserves_beta_and_method_limits(self) -> None:
        snapshot = {
            "version": "0.2",
            "generated_at_local": "2026-08-24T18:00:00-04:00",
            "status": "ok",
            "available_blocks": 3,
            "total_blocks": 3,
            "blocks": {
                "production": {
                    "status": "ok", "safra": "2025/26", "levantamento": 11,
                    "area_mil_ha": 13006.2, "produtividade_kg_ha": 3969.0,
                    "producao_mil_t": 51621.6, "producao_var_pct": 0.6,
                    "data_publicacao": "2026-08-13T12:00:00+00:00",
                    "revision_vs_previous_levantamento": {"previous_levantamento": 10, "producao_revision_mil_t": 100.0, "producao_revision_pct": 0.2},
                    "revision_history": [],
                },
                "storage": {"status": "ok", "warehouse_records_mt": 2920, "municipalities_mt": 107, "capacidade_estatica_mt_t": 58686000.0, "records_with_quality_flags": 0},
                "climate": {
                    "status": "ok", "sample_count": 7, "grid_points_total": 132,
                    "rain_7d_mean_mm": 2.0, "rain_previous_7d_mean_mm": 10.0, "rain_change_pct": -80.0,
                    "eto_hargreaves_7d_mean_mm": 40.0, "rain_minus_eto_7d_mean_mm": -38.0,
                    "gdd_base10_7d_mean": 120.0, "temperature_mean_c": 29.0,
                    "temperature_max_daily_mean_c": 35.0, "relative_humidity_mean_pct": 49.0,
                    "climatic_water_gap_signal": "demanda_atmosferica_acima_da_chuva",
                },
            },
            "limitations": ["Rain minus ET0 e um gap climatico atmosferico, nao deficit de agua no solo."],
        }
        rendered = render_markdown(snapshot)
        self.assertIn("Beta V0.2", rendered)
        self.assertIn("ET0 Hargreaves", rendered)
        self.assertIn("não água disponível no solo", rendered)
        self.assertIn("research_only", rendered)


if __name__ == "__main__":
    unittest.main()
