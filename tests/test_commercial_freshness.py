from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from gateway.commercial_freshness import component_freshness


class CommercialFreshnessTests(unittest.TestCase):
    def test_empty_component_is_failed(self) -> None:
        status, latest, age = component_freshness("weather", [])
        self.assertEqual(status, "FAILED")
        self.assertIsNone(latest)
        self.assertIsNone(age)

    def test_component_without_collection_timestamp_fails_closed(self) -> None:
        status, _, _ = component_freshness("weather", [{"value": 1}])
        self.assertEqual(status, "FAILED")

    def test_weather_component_is_fresh_inside_threshold(self) -> None:
        now = datetime(2026, 10, 9, 3, tzinfo=UTC)
        status, latest, age = component_freshness(
            "weather",
            [{"collection_time": (now - timedelta(minutes=60)).isoformat()}],
            now=now,
        )
        self.assertEqual(status, "FRESH")
        self.assertIsNotNone(latest)
        self.assertEqual(age, 60.0)

    def test_weather_component_is_stale_outside_threshold(self) -> None:
        now = datetime(2026, 10, 9, 3, tzinfo=UTC)
        status, _, age = component_freshness(
            "weather",
            [{"collection_time": (now - timedelta(minutes=721)).isoformat()}],
            now=now,
        )
        self.assertEqual(status, "STALE")
        self.assertEqual(age, 721.0)


if __name__ == "__main__":
    unittest.main()
