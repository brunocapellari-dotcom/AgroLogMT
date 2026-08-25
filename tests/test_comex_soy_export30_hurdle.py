from __future__ import annotations

import unittest

from scripts.build_comex_soy_export30_hurdle import _rows, month_range


class ComexExport30HurdleTests(unittest.TestCase):
    def test_month_range_crosses_year(self) -> None:
        self.assertEqual(month_range(2025, 11, 2026, 2), ["2025-11", "2025-12", "2026-01", "2026-02"])

    def test_month_range_rejects_reverse(self) -> None:
        with self.assertRaises(ValueError):
            month_range(2026, 2, 2025, 12)

    def test_rows_accepts_nested_list(self) -> None:
        payload = {"success": True, "data": {"list": [{"state": "Mato Grosso"}]}}
        self.assertEqual(_rows(payload)[0]["state"], "Mato Grosso")

    def test_rows_rejects_unknown_shape(self) -> None:
        with self.assertRaises(RuntimeError):
            _rows({"success": True, "data": {"unexpected": []}})


if __name__ == "__main__":
    unittest.main()
