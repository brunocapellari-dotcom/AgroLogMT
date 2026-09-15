from __future__ import annotations

import json
import unittest
from pathlib import Path

from collector.ibge_ppm import SOURCE_ID as PPM_SOURCE_ID
from collector.ibge_slaughter import SOURCE_ID as SLAUGHTER_SOURCE_ID

CONFIG = Path("collector/config/sources.pecuaria.json")
EXPECTED_BEEF_NCM = {
    "02011000", "02012010", "02012020", "02012090", "02013000",
    "02021000", "02022010", "02022020", "02022090", "02023000",
}


class PecuariaSourceConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]
        cls.by_id = {source["source_id"]: source for source in cls.sources}

    def test_ppm_source_is_canonical_full_history(self) -> None:
        source = self.by_id[PPM_SOURCE_ID]
        self.assertTrue(source["enabled"])
        self.assertEqual(source["method"], "http")
        self.assertIn("/t/3939/", source["url"])
        self.assertIn("/p/all/", source["url"])
        self.assertEqual(source["evidence_class"], "observado")

    def test_slaughter_source_locks_total_quarter_and_bovine_scope(self) -> None:
        source = self.by_id[SLAUGHTER_SOURCE_ID]
        self.assertTrue(source["enabled"])
        self.assertEqual(source["method"], "http")
        self.assertEqual(source["expected_frequency"], "quarterly")
        self.assertIn("/t/1092/", source["url"])
        self.assertIn("/v/284,285/", source["url"])
        self.assertIn("/c12716/115236", source["url"])
        self.assertIn("/c12529/118225", source["url"])
        self.assertIn("/c18/992", source["url"])
        self.assertEqual(source["evidence_class"], "observado")

    def test_beef_current_source_matches_contract_scope(self) -> None:
        source = self.by_id["mdic_comexstat_beef_mt_export_api"]
        self.assertTrue(source["enabled"])
        self.assertEqual(source["method"], "comexstat_api")
        filters = {item["filter"]: item["values"] for item in source["options"]["filters"]}
        actual = {str(value).zfill(8) for value in filters["ncm"]}
        self.assertEqual(actual, EXPECTED_BEEF_NCM)
        self.assertEqual(filters["state"], [52])
        self.assertEqual(source["options"]["flow"], "export")

    def test_source_ids_are_unique(self) -> None:
        ids = [source["source_id"] for source in self.sources]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
