from __future__ import annotations

import json
import unittest
from pathlib import Path


CANDIDATES = Path("collector/config/maritime_port_boundary_candidates.v1.geojson")


class MaritimePortBoundaryCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CANDIDATES.read_text(encoding="utf-8"))

    def test_candidates_are_never_runtime_geofences(self) -> None:
        self.assertFalse(self.payload["runtime_eligible"])
        self.assertIn("not APPROACH", self.payload["notice"])
        for feature in self.payload["features"]:
            props = feature["properties"]
            self.assertFalse(props["runtime_eligible"])
            self.assertNotEqual(props["status"], "GEOFENCE_VALIDATED")
            self.assertEqual(props["boundary_type"], "PORT_ORGANIZED")

    def test_only_geometry_that_passed_preliminary_topology_is_persisted(self) -> None:
        ports = {feature["properties"]["port_id"] for feature in self.payload["features"]}
        self.assertEqual(ports, {"BARCARENA_VILA_DO_CONDE", "ITAQUI"})
        self.assertNotIn("SANTAREM", ports)
        self.assertNotIn("SANTOS", ports)
        self.assertNotIn("PARANAGUA", ports)

    def test_geojson_rings_are_closed_physical_and_non_degenerate(self) -> None:
        for feature in self.payload["features"]:
            self.assertEqual(feature["geometry"]["type"], "Polygon")
            rings = feature["geometry"]["coordinates"]
            self.assertEqual(len(rings), 1)
            ring = rings[0]
            self.assertGreaterEqual(len(ring), 4)
            self.assertEqual(ring[0], ring[-1])

            area2 = 0.0
            for index in range(len(ring) - 1):
                lon_a, lat_a = map(float, ring[index])
                lon_b, lat_b = map(float, ring[index + 1])
                self.assertGreaterEqual(lat_a, -90)
                self.assertLessEqual(lat_a, 90)
                self.assertGreaterEqual(lon_a, -180)
                self.assertLessEqual(lon_a, 180)
                area2 += lon_a * lat_b - lon_b * lat_a
            self.assertGreater(abs(area2) / 2.0, 1e-12)

    def test_itaqui_remains_blocked_for_currency_review(self) -> None:
        itaqui = next(
            feature for feature in self.payload["features"]
            if feature["properties"]["port_id"] == "ITAQUI"
        )
        self.assertEqual(itaqui["properties"]["status"], "PENDING_CURRENCY_REVIEW")
        self.assertIn("superseding", itaqui["properties"]["qa_note"])


if __name__ == "__main__":
    unittest.main()
