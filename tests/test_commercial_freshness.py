from __future__ import annotations

import unittest
from gateway.freshness import component_freshness


class CommercialFreshnessTests(unittest.TestCase):
    def test_empty_component_is_failed(self) -> None:
        status, latest, age = component_freshness("weather", [])
        self.assertEqual(status, "FAILED")
        self.assertIsNone(latest)
        self.assertIsNone(age)

    def test_component_without_collection_timestamp_fails_closed(self) -> None:
        status, _, _ = component_freshness("weather", [{"value": 1}])
        self.assertEqual(status, "FAILED")


if __name__ == "__main__":
    unittest.main()
