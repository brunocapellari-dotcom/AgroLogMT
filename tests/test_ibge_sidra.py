from __future__ import annotations

import unittest

from collector.ibge_sidra import parse_sidra_number


class IbgeSidraTests(unittest.TestCase):
    def test_numeric_parser_handles_brazilian_formats(self) -> None:
        self.assertEqual(parse_sidra_number("160.000"), 160000.0)
        self.assertEqual(parse_sidra_number("1.234,5"), 1234.5)
        self.assertEqual(parse_sidra_number("1234,5"), 1234.5)
        self.assertEqual(parse_sidra_number("1234"), 1234.0)

    def test_numeric_parser_preserves_missing_and_rejects_non_finite(self) -> None:
        for value in (None, "", "-", "...", "..", "X", "nan", "inf"):
            self.assertIsNone(parse_sidra_number(value))


if __name__ == "__main__":
    unittest.main()
