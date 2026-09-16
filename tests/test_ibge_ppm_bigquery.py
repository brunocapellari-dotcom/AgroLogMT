from __future__ import annotations

import unittest

from collector.ibge_ppm_bigquery import IbgePpmBigQueryLoader, _safe_identifier


class IbgePpmBigQueryTests(unittest.TestCase):
    def test_identifiers_fail_closed(self) -> None:
        self.assertEqual(_safe_identifier("pecuaria", "dataset"), "pecuaria")
        with self.assertRaises(ValueError):
            _safe_identifier("pecuaria.prod", "dataset")

    def test_rows_require_consistent_snapshot_and_pit_guard(self) -> None:
        rows = [
            {
                "snapshot_id": "abc",
                "record_id": "r1",
                "point_in_time_feature_eligible": False,
            },
            {
                "snapshot_id": "abc",
                "record_id": "r2",
                "point_in_time_feature_eligible": False,
            },
        ]
        IbgePpmBigQueryLoader._validate_rows(rows, "abc")

        bad_snapshot = [dict(rows[0], snapshot_id="other")]
        with self.assertRaisesRegex(ValueError, "snapshot_id"):
            IbgePpmBigQueryLoader._validate_rows(bad_snapshot, "abc")

        leaked = [dict(rows[0], point_in_time_feature_eligible=True)]
        with self.assertRaisesRegex(ValueError, "point-in-time"):
            IbgePpmBigQueryLoader._validate_rows(leaked, "abc")

    def test_duplicate_record_id_is_rejected(self) -> None:
        rows = [
            {"snapshot_id": "abc", "record_id": "same", "point_in_time_feature_eligible": False},
            {"snapshot_id": "abc", "record_id": "same", "point_in_time_feature_eligible": False},
        ]
        with self.assertRaisesRegex(ValueError, "duplicado"):
            IbgePpmBigQueryLoader._validate_rows(rows, "abc")


if __name__ == "__main__":
    unittest.main()
