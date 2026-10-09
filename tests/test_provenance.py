from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.provenance import freshness_status


class ProvenanceTests(unittest.TestCase):
    def test_fresh_stale_failed_states(self) -> None:
        now = datetime(2026, 10, 7, 14, 0, tzinfo=timezone.utc)
        self.assertEqual(freshness_status(collection_date="2026-10-07T13:30:00+00:00", max_age_minutes=60, now=now), "FRESH")
        self.assertEqual(freshness_status(collection_date="2026-10-07T10:00:00+00:00", max_age_minutes=60, now=now), "STALE")
        self.assertEqual(freshness_status(collection_date=None, max_age_minutes=60, now=now), "FAILED")


if __name__ == "__main__":
    unittest.main()
