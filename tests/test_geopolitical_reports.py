from __future__ import annotations

import json
import unittest

from collector.geopolitical import GeopoliticalEvent, cluster_events
from collector.geopolitical_bigquery import deterministic_cluster_id
from collector.geopolitical_reports import build_geopolitical_report, corroboration_status, render_geopolitical_report_markdown
from collector.geopolitical_sources import parse_reliefweb_payload


class GeopoliticalReportTests(unittest.TestCase):
    def _news_event(self, event_id: str, source_id: str, domain: str) -> GeopoliticalEvent:
        return GeopoliticalEvent(
            event_id=event_id,
            source_id=source_id,
            source_event_id=f"https://{domain}/{event_id}",
            title="Missile attack disrupts major port operations",
            event_type="media_report",
            data_referencia="2026-08-24T10:00:00+00:00",
            data_publicacao="2026-08-24T10:00:00+00:00",
            data_coleta="2026-08-24T10:05:00+00:00",
            verification_level="osint_signal",
            source_url=f"https://{domain}/{event_id}",
            impact_areas=("shipping", "logistics"),
        )

    def test_report_includes_related_news_with_links_and_publishers(self) -> None:
        first = self._news_event("a", "gdelt_conflict_watch", "reuters.com")
        second = self._news_event("b", "gdelt_conflict_watch_alt", "bbc.com")
        cluster = cluster_events([first, second])[0]
        report = build_geopolitical_report([cluster], generated_at="2026-08-24T11:00:00+00:00")
        event = report["events"][0]
        self.assertEqual(event["news_count"], 2)
        self.assertEqual({item["publisher"] for item in event["news"]}, {"reuters.com", "bbc.com"})
        self.assertEqual(event["corroboration_status"], "multi_publisher_osint")
        markdown = render_geopolitical_report_markdown(report)
        self.assertIn("### Noticias relacionadas", markdown)
        self.assertIn("https://reuters.com/a", markdown)
        self.assertIn("https://bbc.com/b", markdown)

    def test_same_publisher_does_not_become_multi_publisher_corroboration(self) -> None:
        first = self._news_event("a", "query_a", "example.com")
        second = self._news_event("b", "query_b", "example.com")
        cluster = cluster_events([first, second])[0]
        self.assertEqual(corroboration_status(cluster), "single_publisher_osint")

    def test_reliefweb_is_curated_report(self) -> None:
        payload = json.dumps(
            {
                "data": [
                    {
                        "id": "12345",
                        "fields": {
                            "title": "Conflict situation report: port and fuel disruption",
                            "url": "https://reliefweb.int/report/test",
                            "origin": "https://ocha.example/report.pdf",
                            "date": {"created": "2026-08-24T09:00:00+00:00"},
                            "primary_country": {"name": "Testland"},
                            "source": [{"shortname": "OCHA", "name": "UN Office"}]
                        }
                    }
                ]
            }
        ).encode("utf-8")
        events = parse_reliefweb_payload(payload, "reliefweb_fixture", collected_at="2026-08-24T09:05:00+00:00")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.verification_level, "curated_report")
        self.assertEqual(event.country, "Testland")
        self.assertEqual(event.actors, ("OCHA",))
        self.assertIn("shipping", event.impact_areas)
        self.assertIn("energy", event.impact_areas)

    def test_cluster_id_is_order_independent(self) -> None:
        first = self._news_event("a", "a", "a.example")
        second = self._news_event("b", "b", "b.example")
        one = cluster_events([first, second])[0]
        two = cluster_events([second, first])[0]
        self.assertEqual(deterministic_cluster_id(one), deterministic_cluster_id(two))


if __name__ == "__main__":
    unittest.main()
