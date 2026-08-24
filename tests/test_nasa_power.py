from __future__ import annotations

import unittest
from datetime import date

from collector.nasa_power import build_url, parse_response


class NasaPowerTests(unittest.TestCase):
    def test_build_url_uses_ag_community_and_daily_window(self) -> None:
        url = build_url(latitude=-13.05, longitude=-55.92, start=date(2026, 8, 1), end=date(2026, 8, 2))
        self.assertIn("community=AG", url)
        self.assertIn("start=20260801", url)
        self.assertIn("end=20260802", url)
        self.assertIn("PRECTOTCORR", url)

    def test_parse_preserves_gridded_evidence_type(self) -> None:
        payload = {
            "geometry": {"coordinates": [-55.92, -13.05, 350]},
            "properties": {"parameter": {
                "PRECTOTCORR": {"20260801": 3.5, "20260802": -999.0},
                "T2M": {"20260801": 28.1, "20260802": 27.0},
            }},
            "parameters": {
                "PRECTOTCORR": {"units": "mm/day"},
                "T2M": {"units": "C"},
            },
        }
        rows = parse_response(payload)
        self.assertEqual(len(rows), 4)
        rain = [r for r in rows if r.parameter == "PRECTOTCORR"]
        self.assertEqual(rain[0].value, 3.5)
        self.assertIsNone(rain[1].value)
        self.assertTrue(all(r.evidence_subtype == "nasa_power_gridded" for r in rows))
        self.assertTrue(all(r.evidence_class == "estimado" for r in rows))


if __name__ == "__main__":
    unittest.main()
