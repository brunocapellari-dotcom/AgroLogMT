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

    def test_methodology_and_limitations_are_never_silently_missing(self) -> None:
        sections = build_report_sections({"components": []})
        self.assertEqual(sections["Metodologia"].status, "READY")
        self.assertEqual(sections["Limitações"].status, "READY")


if __name__ == "__main__":
    unittest.main()
