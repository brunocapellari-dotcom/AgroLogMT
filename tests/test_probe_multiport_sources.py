from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.probe_multiport_sources import classify_page_freshness, extract_visible_dates


NOW = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


class PortSourceProbeTests(unittest.TestCase):
    def test_extracts_supported_date_formats_and_deduplicates(self) -> None:
        values = extract_visible_dates("24/08/2026 x 2026-08-25 x 24/08/2026")
        self.assertEqual([value.isoformat() for value in values], ["2026-08-24", "2026-08-25"])

    def test_recent_non_future_date_marks_page_recent(self) -> None:
        result = classify_page_freshness("LINE-UP 24/08/2026", collected_at=NOW, freshness_days=4)
        self.assertEqual(result["latest_visible_non_future_date"], "2026-08-24")
        self.assertEqual(result["page_freshness_state"], "RECENT_VISIBLE_DATE")

    def test_future_eta_alone_is_not_page_freshness_proof(self) -> None:
        result = classify_page_freshness("ETA 02/09/2026", collected_at=NOW, freshness_days=4)
        self.assertIsNone(result["latest_visible_non_future_date"])
        self.assertEqual(result["page_freshness_state"], "STALE_OR_NO_VISIBLE_DATE")
        self.assertEqual(result["future_dates_seen"], ["2026-09-02"])

    def test_stale_historical_date_does_not_mark_page_recent(self) -> None:
        result = classify_page_freshness("Atualizado 10/08/2026", collected_at=NOW, freshness_days=4)
        self.assertEqual(result["page_freshness_state"], "STALE_OR_NO_VISIBLE_DATE")

    def test_page_recency_never_claims_validated_port_observation(self) -> None:
        result = classify_page_freshness("25/08/2026", collected_at=NOW, freshness_days=4)
        self.assertNotIn("MULTIPORT_VALIDATED", result.values())

    def test_negative_freshness_window_is_blocked(self) -> None:
        with self.assertRaises(ValueError):
            classify_page_freshness("25/08/2026", collected_at=NOW, freshness_days=-1)


if __name__ == "__main__":
    unittest.main()
