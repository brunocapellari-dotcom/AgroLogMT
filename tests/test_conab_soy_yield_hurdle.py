from __future__ import annotations

import unittest

from scripts.build_conab_soy_yield_hurdle import _season_start


class ConabSoyYieldHurdleTests(unittest.TestCase):
    def test_season_start_accepts_short_and_long_labels(self) -> None:
        self.assertEqual(_season_start("20/21"), 2020)
        self.assertEqual(_season_start("25/26"), 2025)
        self.assertEqual(_season_start("2022/23"), 2022)

    def test_season_start_rejects_invalid_label(self) -> None:
        with self.assertRaises(ValueError):
            _season_start("2025")


if __name__ == "__main__":
    unittest.main()
