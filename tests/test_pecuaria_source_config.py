from __future__ import annotations

import json
import unittest
from pathlib import Path

from collector.ibge_ppm import SOURCE_ID as PPM_SOURCE_ID
from collector.ibge_slaughter import SOURCE_ID as SLAUGHTER_SOURCE_ID
from collector.mapa_sigsif import PACKAGE_ID, RESOURCE_ID, SOURCE_ID as SIGSIF_SOURCE_ID

CONFIG = Path("collector/config/sources.pecuaria.json")
REGISTRY = Path("collector/config/data_source_registry.v1.json")
BEEF_SOURCE_ID = "mdic_comexstat_beef_mt_export_api"
EXPECTED_BEEF_NCM = {
    "02011000", "02012010", "02012020", "02012090", "02013000",
    "02021000", "02022010", "02022020", "02022090", "02023000",
}
EXPECTED_REGISTRY_IDS = {
    PPM_SOURCE_ID,
    SLAUGHTER_SOURCE_ID,
    SIGSIF_SOURCE_ID,
    BEEF_SOURCE_ID,
}


class PecuariaSourceConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = json.loads(CONFIG.read_text(encoding="utf-8"))["sources"]
        cls.by_id = {source["source_id"]: source for source in cls.sources}
        registry_sources = json.loads(REGISTRY.read_text(encoding="utf-8"))["sources"]
        cls.registry_by_id = {source["source_id"]: source for source in registry_sources}

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

    def test_sigsif_uses_official_mapa_ckan_resource_and_stays_crosscheck(self) -> None:
        source = self.by_id[SIGSIF_SOURCE_ID]
        self.assertTrue(source["enabled"])
        self.assertEqual(source["method"], "ckan_resource")
        self.assertEqual(source["expected_frequency"], "monthly")
        self.assertEqual(source["options"]["base_url"], "https://dados.agricultura.gov.br")
        self.assertEqual(source["options"]["dataset_id"], PACKAGE_ID)
        self.assertEqual(source["options"]["resource_id"], RESOURCE_ID)
        self.assertIn("cross-check", source["notes"])
        self.assertIn("não possui competência", source["notes"])

    def test_beef_current_source_matches_contract_scope(self) -> None:
        source = self.by_id[BEEF_SOURCE_ID]
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

    def test_global_registry_has_exact_concrete_livestock_execution_entries(self) -> None:
        cattle = {
            source_id: row
            for source_id, row in self.registry_by_id.items()
            if row.get("domain") == "cattle"
        }
        self.assertEqual(set(cattle), EXPECTED_REGISTRY_IDS)
        self.assertNotIn("ibge_cattle", self.registry_by_id)
        self.assertNotIn("sigsif_cattle", self.registry_by_id)
        for source_id, row in cattle.items():
            self.assertEqual(row["status"], "gated")
            self.assertEqual(row["fallback"], [])
            self.assertTrue(row["trusted_transport"])
            self.assertEqual(
                row["execution_ref"],
                f"collector/config/sources.pecuaria.json#{source_id}",
            )

    def test_registry_and_execution_config_have_one_to_one_source_ids(self) -> None:
        self.assertEqual(set(self.by_id), EXPECTED_REGISTRY_IDS)
        self.assertEqual(
            {source_id for source_id, row in self.registry_by_id.items() if row.get("domain") == "cattle"},
            set(self.by_id),
        )


if __name__ == "__main__":
    unittest.main()
