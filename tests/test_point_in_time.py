from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.point_in_time import available_at, select_as_of


class PointInTimeTests(unittest.TestCase):
    def test_collection_after_publication_controls_availability(self) -> None:
        row = {
            "data_publicacao": "2026-08-13T09:00:00-04:00",
            "data_coleta": "2026-08-13T14:30:00+00:00",
        }
        self.assertEqual(available_at(row), datetime(2026, 8, 13, 14, 30, tzinfo=timezone.utc))

    def test_future_revision_does_not_leak(self) -> None:
        rows = [
            {"produto": "soja", "safra": "2025/26", "valor": 50, "data_publicacao": "2026-07-01T12:00:00+00:00", "data_coleta": "2026-07-01T12:10:00+00:00", "revision": 1},
            {"produto": "soja", "safra": "2025/26", "valor": 55, "data_publicacao": "2026-08-01T12:00:00+00:00", "data_coleta": "2026-08-01T12:10:00+00:00", "revision": 2},
        ]
        chosen = select_as_of(
            rows,
            cutoff=datetime(2026, 7, 15, tzinfo=timezone.utc),
            key_fields=("produto", "safra"),
            revision_field="revision",
        )
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["valor"], 50)

    def test_latest_available_revision_wins(self) -> None:
        rows = [
            {"k": "a", "value": 1, "data_publicacao": "2026-01-01T00:00:00+00:00", "data_coleta": "2026-01-01T01:00:00+00:00"},
            {"k": "a", "value": 2, "data_publicacao": "2026-02-01T00:00:00+00:00", "data_coleta": "2026-02-01T01:00:00+00:00"},
        ]
        chosen = select_as_of(rows, cutoff=datetime(2026, 3, 1, tzinfo=timezone.utc), key_fields=("k",))
        self.assertEqual(chosen[0]["value"], 2)


if __name__ == "__main__":
    unittest.main()
