from __future__ import annotations

import unittest

from collector.ibge_slaughter_bigquery import (
    HEAD_METRIC,
    WEIGHT_METRIC,
    IbgeSlaughterBigQueryLoader,
)


class IbgeSlaughterBigQueryTests(unittest.TestCase):
    def _rows(self):
        base = {
            "snapshot_id": "abc",
            "year": 2024,
            "quarter": 1,
            "point_in_time_feature_eligible": False,
        }
        return [
            dict(base, record_id="r1", metric_id=HEAD_METRIC, value=1000.0),
            dict(base, record_id="r2", metric_id=WEIGHT_METRIC, value=250000.0),
        ]

    def test_rows_require_both_official_metrics(self) -> None:
        IbgeSlaughterBigQueryLoader._validate_rows(self._rows(), "abc")
        with self.assertRaisesRegex(ValueError, "duas métricas"):
            IbgeSlaughterBigQueryLoader._validate_rows(self._rows()[:1], "abc")

    def test_snapshot_and_point_in_time_guards_fail_closed(self) -> None:
        rows = self._rows()
        rows[0]["snapshot_id"] = "other"
        with self.assertRaisesRegex(ValueError, "snapshot_id"):
            IbgeSlaughterBigQueryLoader._validate_rows(rows, "abc")

        rows = self._rows()
        rows[0]["point_in_time_feature_eligible"] = True
        with self.assertRaisesRegex(ValueError, "point-in-time"):
            IbgeSlaughterBigQueryLoader._validate_rows(rows, "abc")

    def test_unknown_metric_and_duplicate_id_are_rejected(self) -> None:
        rows = self._rows()
        rows[0]["metric_id"] = "pecuaria.inventada"
        with self.assertRaisesRegex(ValueError, "fora do contrato"):
            IbgeSlaughterBigQueryLoader._validate_rows(rows, "abc")

        rows = self._rows()
        rows[1]["record_id"] = rows[0]["record_id"]
        with self.assertRaisesRegex(ValueError, "duplicado"):
            IbgeSlaughterBigQueryLoader._validate_rows(rows, "abc")


if __name__ == "__main__":
    unittest.main()
