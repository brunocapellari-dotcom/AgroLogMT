from __future__ import annotations

import json
import unittest
from pathlib import Path


CONFIG = Path("collector/config/maritime_ais_subscription.v1.json")
EXPECTED_PORTS = {
    "SANTOS",
    "PARANAGUA",
    "BARCARENA_VILA_DO_CONDE",
    "SANTAREM",
    "ITAQUI",
}


class MaritimeSubscriptionConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_pilot_has_exactly_five_canonical_ports(self) -> None:
        self.assertEqual(set(self.payload["pilot_ports"]), EXPECTED_PORTS)
        self.assertEqual({row["port_id"] for row in self.payload["areas"]}, EXPECTED_PORTS)

    def test_subscription_boxes_are_valid_but_not_geofences(self) -> None:
        rules = " ".join(self.payload["hard_rules"]).upper()
        self.assertIn("NENHUMA CLASSIFICACAO", rules)
        self.assertIn("GEOFENCE", rules)

        for area in self.payload["areas"]:
            box = area["bounding_box"]
            self.assertEqual(len(box), 2)
            south_west, north_east = box
            self.assertEqual(len(south_west), 2)
            self.assertEqual(len(north_east), 2)
            south, west = map(float, south_west)
            north, east = map(float, north_east)
            self.assertLess(south, north)
            self.assertLess(west, east)
            self.assertGreaterEqual(south, -90)
            self.assertLessEqual(north, 90)
            self.assertGreaterEqual(west, -180)
            self.assertLessEqual(east, 180)

            lat, lon = map(float, area["reference_point"])
            self.assertGreaterEqual(lat, south)
            self.assertLessEqual(lat, north)
            self.assertGreaterEqual(lon, west)
            self.assertLessEqual(lon, east)
            self.assertTrue(area["reference_source"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
