from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from collector.adapters import get_adapter
from collector.geopolitical import (
    GeopoliticalEvent,
    cluster_events,
    infer_agrolog_impact_areas,
    parse_gdelt_doc_payload,
    parse_ucdp_payload,
    score_cluster,
)
from collector.models import SourceSpec


class GeopoliticalWatchTests(unittest.TestCase):
    def test_ucdp_normalization_preserves_research_coded_evidence(self) -> None:
        payload = json.dumps(
            {
                "Result": [
                    {
                        "id": 123,
                        "type_of_violence": 1,
                        "dyad_name": "Government of Testland - Armed Group",
                        "side_a": "Government of Testland",
                        "side_b": "Armed Group",
                        "country": "Testland",
                        "region": "Test Region",
                        "latitude": 10.5,
                        "longitude": 20.5,
                        "date_start": "2026-08-23",
                        "best": 12
                    }
                ]
            }
        ).encode("utf-8")

        events = parse_ucdp_payload(payload, "ucdp_fixture", collected_at="2026-08-24T12:00:00+00:00")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.verification_level, "research_coded")
        self.assertEqual(event.evidence_class, "observado")
        self.assertEqual(event.fatalities_best, 12)
        self.assertEqual(event.actors, ("Government of Testland", "Armed Group"))

    def test_gdelt_is_osint_signal_not_confirmed_fact(self) -> None:
        payload = json.dumps(
            {
                "articles": [
                    {
                        "title": "Missile attack disrupts port operations",
                        "url": "https://example.org/report-1",
                        "seendate": "20260824T101500Z"
                    }
                ]
            }
        ).encode("utf-8")
        events = parse_gdelt_doc_payload(payload, "gdelt_fixture", collected_at="2026-08-24T10:20:00+00:00")
        self.assertEqual(events[0].verification_level, "osint_signal")
        self.assertIn("shipping", events[0].impact_areas)
        self.assertIn("logistics", events[0].impact_areas)
        self.assertEqual(events[0].impact_evidence_class, "inferido")

    def test_cluster_corroboration_raises_priority(self) -> None:
        common = dict(
            source_event_id=None,
            event_type="media_report",
            data_referencia="2026-08-24T10:00:00+00:00",
            data_publicacao="2026-08-24T10:00:00+00:00",
            data_coleta="2026-08-24T10:05:00+00:00",
            evidence_class="observado",
            verification_level="osint_signal",
            impact_areas=("shipping",),
        )
        first = GeopoliticalEvent(
            event_id="a",
            source_id="source_a",
            title="Missile attack disrupts major port operations",
            **common,
        )
        second = GeopoliticalEvent(
            event_id="b",
            source_id="source_b",
            title="Missile attack disrupts major port operations",
            **common,
        )
        single_score = score_cluster(cluster_events([first])[0])
        corroborated = cluster_events([first, second])[0]
        self.assertEqual(corroborated.source_count, 2)
        self.assertGreater(score_cluster(corroborated), single_score)

    def test_impact_tagging_is_conservative_and_explicit(self) -> None:
        impacts = infer_agrolog_impact_areas("Port blockade affects grain and crude tanker traffic")
        self.assertIn("shipping", impacts)
        self.assertIn("trade", impacts)
        self.assertIn("agriculture", impacts)
        self.assertIn("energy", impacts)

    def test_env_header_adapter_requires_secret_outside_git(self) -> None:
        spec = SourceSpec(
            source_id="ucdp_fixture",
            name="UCDP fixture",
            group="dados",
            method="http_env_header",
            url="https://example.org",
            options={
                "header_name": "x-ucdp-access-token",
                "header_env_var": "UCDP_API_TOKEN_TEST"
            }
        )
        env = dict(os.environ)
        env.pop("UCDP_API_TOKEN_TEST", None)
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "UCDP_API_TOKEN_TEST"):
                get_adapter("http_env_header").fetch(spec)


if __name__ == "__main__":
    unittest.main()
