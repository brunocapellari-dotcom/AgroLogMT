from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts import generate_soy_mt_beta as beta01
from scripts.run_soy_mt_beta import MT_TIMEZONE, configure_mt_timezone


class SoyMtTimezoneTests(unittest.TestCase):
    def test_runtime_uses_cuiaba_timezone(self) -> None:
        configure_mt_timezone()
        self.assertEqual(MT_TIMEZONE, "America/Cuiaba")
        converted = datetime(2026, 8, 24, 22, 20, tzinfo=timezone.utc).astimezone(beta01.SAO_PAULO)
        self.assertEqual(converted.hour, 18)
        self.assertEqual(converted.utcoffset().total_seconds(), -4 * 3600)


if __name__ == "__main__":
    unittest.main()
