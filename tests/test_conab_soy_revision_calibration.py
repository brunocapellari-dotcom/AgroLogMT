from __future__ import annotations

import unittest

from scripts.analyze_conab_soy_revision_calibration import (
    RevisionPoint,
    aggregate_by_levantamento,
    build_revision_errors,
    current_revision_state,
)


class ConabSoyRevisionCalibrationTests(unittest.TestCase):
    def _points(self):
        return [
            RevisionPoint("2022/23", 10, "2023-07-10T12:00:00+00:00", 1000.0, 3500.0, 3500.0, "registry_attachment"),
            RevisionPoint("2022/23", 11, "2023-08-10T12:00:00+00:00", 1010.0, 3550.0, 3585.5, "registry_attachment"),
            RevisionPoint("2022/23", 12, "2023-09-01T12:00:00+00:00", 1020.0, 3600.0, 3672.0, "registry_attachment"),
            RevisionPoint("2024/25", 10, "2025-07-10T12:00:00+00:00", 1100.0, 3900.0, 4290.0, "registry_attachment"),
            RevisionPoint("2024/25", 11, "2025-08-14T12:00:00+00:00", 1110.0, 3950.0, 4384.5, "registry_attachment"),
            RevisionPoint("2024/25", 12, "2025-09-11T12:00:00+00:00", 1120.0, 4000.0, 4480.0, "registry_attachment"),
            RevisionPoint("2025/26", 10, "2026-07-14T12:00:00+00:00", 1200.0, 3960.0, 4752.0, "registry_attachment"),
            RevisionPoint("2025/26", 11, "2026-08-13T12:00:00+00:00", 1200.0, 3970.0, 4764.0, "registry_attachment"),
        ]

    def test_errors_use_12th_as_reference_only(self):
        errors = build_revision_errors(self._points())
        self.assertEqual(len(errors), 4)
        self.assertEqual({row["safra"] for row in errors}, {"2022/23", "2024/25"})
        ten = [row for row in errors if row["levantamento"] == 10]
        self.assertEqual(len(ten), 2)
        self.assertEqual(ten[0]["yield_error_kg_ha"], -100.0)

    def test_aggregation_refuses_interval_with_less_than_five_seasons(self):
        calibration = aggregate_by_levantamento(build_revision_errors(self._points()))
        self.assertEqual(calibration["10"]["n_seasons"], 2)
        self.assertFalse(calibration["10"]["interval_eligible"])

    def test_current_revision_state_uses_latest_publication_season(self):
        current = current_revision_state(self._points())
        self.assertEqual(current["safra"], "2025/26")
        self.assertEqual(current["latest_levantamento"], 11)
        self.assertEqual(current["revision_vs_previous"]["yield_revision_kg_ha"], 10.0)


if __name__ == "__main__":
    unittest.main()
