from __future__ import annotations

import unittest

from models.agrolog_intelligence_report import (
    CRITICAL_SECTIONS,
    SECTION_ORDER,
    ReportSection,
    evaluate_sellability,
    render_markdown,
)


class AgroLogIntelligenceReportTests(unittest.TestCase):
    def _complete(self):
        return {
            title: ReportSection(
                title=title,
                status="READY",
                summary=f"Resumo {title}",
                bullets=("Evidência material.",),
                source_ids=("source",),
            )
            for title in SECTION_ORDER
        }

    def test_renderer_contains_all_30_sections(self) -> None:
        sections = self._complete()
        markdown, gate = render_markdown(sections)
        self.assertEqual(len(SECTION_ORDER), 30)
        for index, title in enumerate(SECTION_ORDER, start=1):
            self.assertIn(f"## {index}. {title}", markdown)
        self.assertEqual(gate.status, "SELLABLE")

    def test_critical_gap_blocks_sellability_but_report_still_renders(self) -> None:
        sections = self._complete()
        sections["Meteorologia"] = ReportSection(
            title="Meteorologia",
            status="FAILED",
            summary="Fonte indisponível.",
        )
        markdown, gate = render_markdown(sections)
        self.assertEqual(gate.status, "BLOCKED")
        self.assertIn("critical_not_ready:Meteorologia:FAILED", gate.blockers)
        self.assertIn("Fonte indisponível.", markdown)


if __name__ == "__main__":
    unittest.main()
