from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from collector.conab_safra_history import (
    SafraPublication,
    discover_archive_by_pattern,
    publication_plausible_for_safra,
)
from scripts.backfill_conab_safra import availability_status, build_plan, merge_publications


class HistoricalAvailabilityTests(unittest.TestCase):
    def test_publication_window_accepts_real_cycle_and_rejects_site_migration(self) -> None:
        self.assertTrue(publication_plausible_for_safra("2022/23", "2023-09-01T12:00:00+00:00"))
        self.assertTrue(publication_plausible_for_safra("2025/26", "2026-08-13T12:00:00+00:00"))
        self.assertFalse(publication_plausible_for_safra("2022/23", "2025-09-17T15:31:00+00:00"))
        self.assertFalse(publication_plausible_for_safra("2022/23", None))

    def test_plan_blocks_missing_migrated_and_evidence_less_timestamps(self) -> None:
        rows = [
            SafraPublication("u1", "a1", "2022/23", 12, "2023-09-01T12:00:00+00:00", "official_page_timestamp"),
            SafraPublication("u2", "a2", "2022/23", 1, "2025-09-17T15:31:00+00:00", None),
            SafraPublication("u3", "a3", "2021/22", 1, None, None),
            SafraPublication("u4", "a4", "2022/23", 2, "2022-11-09T12:00:00+00:00", None),
        ]
        plan = build_plan(rows)
        self.assertEqual(plan[0]["execution_status"], "ready")
        self.assertEqual(plan[0]["availability_basis"], "official_page_timestamp")
        self.assertEqual(plan[1]["execution_status"], "blocked_suspected_site_migration_timestamp")
        self.assertEqual(plan[2]["execution_status"], "blocked_missing_original_publication_time")
        self.assertEqual(plan[3]["execution_status"], "blocked_missing_availability_evidence_basis")

    def test_merge_prefers_verified_timestamp_for_same_identity(self) -> None:
        migrated = SafraPublication("old", "a", "2022/23", 1, "2025-09-17T15:31:00+00:00", None)
        verified = SafraPublication("verified", "b", "2022/23", 1, "2022-10-06T12:00:00+00:00", "official_nested_page_timestamp")
        merged = merge_publications([migrated], [verified])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].item_url, "verified")
        self.assertEqual(availability_status(merged[0]), (True, "ready"))


class ArchiveDiscoveryTests(unittest.TestCase):
    @patch("collector.conab_safra_history._publication_from_item")
    def test_archive_scanner_walks_expected_season_and_ignores_404(self, fetch_item) -> None:
        def side_effect(url: str):
            if "/12o-levantamento-safra-2022-23" in url:
                return SafraPublication(url, url + "/file.xlsx", "2022/23", 12, "2023-09-01T12:00:00+00:00", "official_page_timestamp")
            raise HTTPError(url, 404, "not found", hdrs=None, fp=None)

        fetch_item.side_effect = side_effect
        rows = discover_archive_by_pattern(start_year=2022, end_year=2022)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].safra, rows[0].levantamento), ("2022/23", 12))
        self.assertEqual(fetch_item.call_count, 12)


if __name__ == "__main__":
    unittest.main()
