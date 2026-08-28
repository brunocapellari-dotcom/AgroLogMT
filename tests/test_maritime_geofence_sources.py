from __future__ import annotations

import json
import unittest
from pathlib import Path


CONFIG = Path("collector/config/maritime_geofence_sources.v1.json")
EXPECTED_PORTS = {
    "SANTOS",
    "PARANAGUA",
    "BARCARENA_VILA_DO_CONDE",
    "SANTAREM",
    "ITAQUI",
}


class MaritimeGeofenceSourceManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_manifest_is_data_gated_and_has_exact_pilot(self) -> None:
        governance = self.payload["governance"]
        self.assertEqual(governance["operational_gate"], "GEOFENCE_VALIDATED")
        self.assertEqual(governance["default_runtime_state"], "DATA_GATED")
        self.assertEqual({row["port_id"] for row in self.payload["ports"]}, EXPECTED_PORTS)

    def test_manifest_contains_sources_not_runtime_geometry(self) -> None:
        forbidden_keys = {"coordinates", "polygon", "geojson", "ring", "geometry"}

        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn(key.lower(), forbidden_keys)
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.payload)

    def test_primary_sources_are_https_and_actions_are_explicit(self) -> None:
        for port in self.payload["ports"]:
            polygon = port["port_polygon"]
            primary = polygon["primary_source"]
            self.assertTrue(primary["url"].startswith("https://"))
            self.assertTrue(primary["status"])
            self.assertTrue(polygon["next_action"])
            self.assertIn("status", port["hydrographic_qa"])
            self.assertTrue(port["hydrographic_qa"]["chart_ids"])
            self.assertTrue(port["berth_geometry"]["next_action"])

    def test_shared_chm_sources_are_not_promoted_to_operational_truth(self) -> None:
        sources = {row["source_id"]: row for row in self.payload["shared_hydrographic_sources"]}
        self.assertEqual(sources["CHM_RASTER_CHARTS"]["status"], "AVAILABLE_FREE_DOWNLOAD")
        self.assertEqual(sources["CHM_ENC"]["status"], "LICENSED_DISTRIBUTION_ONLY")
        rules = " ".join(self.payload["governance"]["hard_rules"]).upper()
        self.assertIn("NÃO DEVE SER VETORIZADA AUTOMATICAMENTE", rules)
        self.assertIn("NUNCA INFERIDO", rules)

    def test_itaqui_transcription_conflict_is_explicit(self) -> None:
        itaqui = next(row for row in self.payload["ports"] if row["port_id"] == "ITAQUI")
        secondary = itaqui["port_polygon"]["secondary_source"]
        self.assertEqual(secondary["status"], "AVAILABLE_WITH_TRANSCRIPTION_ERROR")
        self.assertIn("M F", secondary["warning"])
        self.assertIn("44°21’47,0 W", secondary["warning"])
        self.assertEqual(itaqui["port_polygon"]["currency_risk"]["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
