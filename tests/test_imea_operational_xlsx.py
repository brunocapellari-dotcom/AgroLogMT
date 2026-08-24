from __future__ import annotations

import io
import unittest
import zipfile

from collector.imea_operational_xlsx import excel_date, normalize_unit


class ImeaOperationalTests(unittest.TestCase):
    def test_excel_date(self) -> None:
        self.assertEqual(excel_date(44928), "2023-01-02")

    def test_unit_normalization(self) -> None:
        self.assertEqual(normalize_unit("R$/T"), "R$/t")
        self.assertEqual(normalize_unit("R$/sc"), "R$/sc")


if __name__ == "__main__":
    unittest.main()
