from __future__ import annotations

import json
import unittest
from pathlib import Path
from urllib.parse import urlsplit


class UsdaFasConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payload = json.loads(Path("collector/config/sources.pilot.json").read_text(encoding="utf-8"))
        cls.sources = {
            item["source_id"]: item
            for item in payload["sources"]
            if item["source_id"].startswith("usda_fas_")
        }

    def test_expected_fas_specs_are_registered(self):
        self.assertEqual(
            set(self.sources),
            {
                "usda_fas_psd_commodities",
                "usda_fas_psd_countries",
                "usda_fas_psd_attributes",
                "usda_fas_esr_release_dates",
                "usda_fas_esr_commodities",
                "usda_fas_gats_census_exports_release_dates",
                "usda_fas_gats_census_imports_release_dates",
            },
        )

    def test_fas_specs_use_canonical_env_header_adapter_and_no_literal_secret(self):
        raw = Path("collector/config/sources.pilot.json").read_text(encoding="utf-8")
        self.assertNotIn("DEMO_KEY", raw)
        self.assertNotIn("api_key=", raw.lower())
        for spec in self.sources.values():
            self.assertEqual(spec["method"], "http_env_header")
            self.assertFalse(spec["enabled"])
            self.assertEqual(spec["options"]["header_name"], "X-Api-Key")
            self.assertEqual(spec["options"]["header_env_var"], "DATA_GOV_API_KEY")
            self.assertEqual(spec["options"]["headers"].get("Accept"), "application/json")

    def test_fas_urls_are_https_and_locked_to_official_host(self):
        for spec in self.sources.values():
            parts = urlsplit(spec["url"])
            self.assertEqual(parts.scheme, "https")
            self.assertEqual(parts.hostname, "api.fas.usda.gov")
            self.assertNotIn("key", parts.query.lower())

    def test_fas_specs_remain_data_sources_with_observed_api_metadata(self):
        for spec in self.sources.values():
            self.assertEqual(spec["group"], "dados")
            self.assertEqual(spec["file_extension"], "json")
            self.assertEqual(spec["evidence_class"], "observado")


if __name__ == "__main__":
    unittest.main()
