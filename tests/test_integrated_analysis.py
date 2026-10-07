from __future__ import annotations

import unittest

from models.integrated_analysis import AnalysisClaim, TrendAssessment


class IntegratedAnalysisTests(unittest.TestCase):
    def test_claim_requires_evidence_mechanism_impact_and_source(self) -> None:
        claim = AnalysisClaim(
            topic="soja_mt",
            evidence_class="observado",
            evidence="chuva 30d abaixo do percentil histórico",
            mechanism="menor reposição hídrica na fase crítica",
            impact_potential="eleva risco de perda de produtividade se persistir",
            horizon="7-15d",
            confidence="media",
            source_ids=("inmet_weather", "conab_safra_graos_xlsx"),
        )
        self.assertEqual(claim.evidence_class, "OBSERVADO")

    def test_claim_without_source_fails(self) -> None:
        with self.assertRaises(ValueError):
            AnalysisClaim(
                topic="x",
                evidence_class="inferido",
                evidence="e",
                mechanism="m",
                impact_potential="i",
                horizon="7d",
                confidence="baixa",
                source_ids=(),
            )

    def test_trends_are_explicitly_typed(self) -> None:
        trend = TrendAssessment(
            topic="frete",
            trend_type="fundamental",
            direction="pressao_altista",
            rationale="mais ofertas de carga e menor folga logística",
            horizon="7d",
            confidence="media",
            source_ids=("whatsapp_freight_authorized",),
        )
        self.assertEqual(trend.trend_type, "FUNDAMENTAL")


if __name__ == "__main__":
    unittest.main()
