from __future__ import annotations

import unittest

from models.agrolog_intelligence_report import evaluate_sellability
from models.commercial_report_builder import build_report_sections


class CommercialReportBuilderTests(unittest.TestCase):
    def test_partial_snapshot_renders_full_structure_and_blocks_sellable(self) -> None:
        snapshot = {
            "components": [
                {"component": "ptax", "source_id": "ptax", "status": "FRESH_OR_SOURCE_DEFINED", "data": [{"cotacao_venda": 5.2}]},
                {"component": "crops_mt", "source_id": "crop", "status": "FRESH_OR_SOURCE_DEFINED", "data": [{"product_id": "soja", "safra": "26/27", "vintage_position": "current", "producao_mil_t": 50_000, "produtividade_kg_ha": 3600}]},
            ]
        }
        sections = build_report_sections(snapshot)
        self.assertEqual(len(sections), 30)
        gate = evaluate_sellability(sections)
        self.assertEqual(gate.status, "BLOCKED")
        self.assertIn("critical_not_ready:Mercado:PARTIAL", gate.blockers)


    def test_commercial_sections_render_concise_lines_not_raw_dicts(self) -> None:
        snapshot = {
            "components": [
                {"component": "usda", "status": "FRESH", "data": [{
                    "commodity_hint": "soja",
                    "path": "wasde/commodity/country/value",
                    "attributes_json": '{"commodity.name":"Soybeans","country.name":"Brazil","value.unit":"million_t"}',
                    "numeric_value": 170.0,
                    "delta_numeric_value": 1.5,
                }]},
                {"component": "argentina", "status": "FRESH", "data": [{
                    "crop_id": "soja", "season": "2026/27", "planted_area_ha": 16_000_000,
                    "production_t": 49_500_000, "yield_kg_ha": 3200, "delta_production_pct": -1.2,
                }]},
                {"component": "exports", "status": "FRESH", "data": [{
                    "product_id": "soja_grao", "competencia": "2026-09", "toneladas": 2_500_000,
                    "delta_toneladas_pct": 8.5, "vl_fob": 1_000_000_000, "usd_por_t": 400,
                }]},
                {"component": "weather", "status": "FRESH", "data": [{
                    "valid_time": "2026-10-10T12:00:00Z", "variable": "precipitation",
                    "model_median": 25, "model_iqr": 8, "unit": "mm", "model_count": 3,
                    "models_with_run_comparison": 2, "models_revised_up": 2, "models_revised_down": 0,
                }]},
                {"component": "weather_3d", "status": "FRESH", "data": [{
                    "valid_time": "2026-10-10T12:00:00Z", "variable": "precipitation",
                    "model_median": 25, "model_iqr": 8, "unit": "mm", "model_count": 3,
                }]},
            ]
        }
        sections = build_report_sections(snapshot)
        for title in ("USDA/EUA", "Argentina", "Exportação", "Meteorologia", "Previsão 3 dias"):
            self.assertTrue(sections[title].bullets, title)
            self.assertFalse(any(str(item).lstrip().startswith("{") for item in sections[title].bullets), title)
        self.assertIn("Brazil", sections["USDA/EUA"].bullets[0])
        self.assertIn("49.50 mi t", sections["Argentina"].bullets[0])
        self.assertIn("2.50 mi t", sections["Exportação"].bullets[0])

    def test_methodology_and_limitations_are_never_silently_missing(self) -> None:
        sections = build_report_sections({"components": []})
        self.assertEqual(sections["Metodologia"].status, "READY")
        self.assertEqual(sections["Limitações"].status, "READY")


if __name__ == "__main__":
    unittest.main()
