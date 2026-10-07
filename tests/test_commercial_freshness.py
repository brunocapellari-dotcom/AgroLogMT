from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from gateway.app import _component_freshness


class CommercialFreshnessTests(unittest.TestCase):
    def test_empty_component_is_failed(self) -> None:
        status, latest, age = _component_freshness("weather", [])
        self.assertEqual(status, "FAILED")
        self.assertIsNone(latest)
        self.assertIsNone(age)

    def test_component_without_collection_timestamp_fails_closed(self) -> None:
        status, _, _ = _component_freshness("weather", [{"value": 1}])
        self.assertEqual(status, "FAILED")


if __name__ == "__main__":
    unittest.main()
