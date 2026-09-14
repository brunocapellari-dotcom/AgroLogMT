from __future__ import annotations

import unittest
from pathlib import Path

from collector.ais_worker import _capture_event


class FakeStore:
    def __init__(self) -> None:
        self.rows = []

    @staticmethod
    def stable_id(*parts):
        return "|".join(str(part) for part in parts)

    def load_ais_capture_event(self, row):
        self.rows.append(row)
        return 1


class AisHistoryCaptureTests(unittest.TestCase):
    def test_capture_event_preserves_run_and_quality_metadata(self) -> None:
        store = FakeStore()
        _capture_event(
            store,
            run_id="run-1",
            event_type="END",
            aoi_count=5,
            capture_seconds=3540,
            records=123,
            details={"zone_count": 2},
        )
        self.assertEqual(len(store.rows), 1)
        row = store.rows[0]
        self.assertEqual(row["event_id"], "run-1|END")
        self.assertEqual(row["run_id"], "run-1")
        self.assertEqual(row["event_type"], "END")
        self.assertEqual(row["aoi_count"], 5)
        self.assertEqual(row["capture_seconds_requested"], 3540)
        self.assertEqual(row["records"], 123)

    def test_deploy_defaults_to_near_continuous_capture(self) -> None:
        script = Path("scripts/deploy_ais_worker_gcloud.sh").read_text(encoding="utf-8")
        self.assertIn('AIS_CAPTURE_SECONDS:-3540', script)
        self.assertIn('--task-timeout 65m', script)
        self.assertIn('"5 * * * *"', script)


if __name__ == "__main__":
    unittest.main()
