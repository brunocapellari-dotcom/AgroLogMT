from __future__ import annotations

import unittest
from datetime import datetime, timezone

from collector.comex_availability import (
    historical_row_is_feature_eligible,
    latest_release_as_of,
    normalize_release,
    snapshot_can_reconstruct_vintage,
)


class ComexAvailabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = normalize_release(
            competence="2026-07",
            release_time="2026-08-06T15:48:00-03:00",
            release_type="monthly_consolidated",
            source_url="https://www.gov.br/mdic/example",
            evidence_basis="official_monthly_release_notice",
        )

    def test_release_normalizes_to_utc(self) -> None:
        self.assertEqual(self.release.release_time, "2026-08-06T18:48:00+00:00")

    def test_feature_is_unavailable_before_release(self) -> None:
        before = datetime(2026, 8, 6, 18, 0, tzinfo=timezone.utc)
        after = datetime(2026, 8, 6, 19, 0, tzinfo=timezone.utc)
        self.assertFalse(historical_row_is_feature_eligible(competence="2026-07", cutoff=before, releases=[self.release]))
        self.assertTrue(historical_row_is_feature_eligible(competence="2026-07", cutoff=after, releases=[self.release]))

    def test_preliminary_release_is_not_consolidated_feature(self) -> None:
        partial = normalize_release(
            competence="2026-08",
            release_time="2026-08-17T15:07:00-03:00",
            release_type="preliminary_partial",
            source_url="https://www.gov.br/mdic/partial",
            evidence_basis="official_partial_release_notice",
        )
        cutoff = datetime(2026, 8, 18, tzinfo=timezone.utc)
        self.assertIsNone(latest_release_as_of([partial], competence="2026-08", cutoff=cutoff, consolidated_only=True))

    def test_late_snapshot_does_not_claim_to_be_original_vintage(self) -> None:
        late = datetime(2026, 8, 12, tzinfo=timezone.utc)
        self.assertTrue(snapshot_can_reconstruct_vintage(snapshot_collected_at=late, release=self.release))
        # This only means the file existed after release; provenance still needs its own snapshot hash.
        early = datetime(2026, 8, 5, tzinfo=timezone.utc)
        self.assertFalse(snapshot_can_reconstruct_vintage(snapshot_collected_at=early, release=self.release))


if __name__ == "__main__":
    unittest.main()
