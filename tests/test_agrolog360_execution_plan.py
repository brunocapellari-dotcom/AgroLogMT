from __future__ import annotations

import unittest
from pathlib import Path

from scripts.agrolog360_readiness import PRIORITY_SOURCE_IDS, build_readiness
from scripts.apply_agrolog360_marts import SOURCE_DEPENDENCIES


ROOT = Path(__file__).resolve().parents[1]


class AgroLog360ExecutionPlanTests(unittest.TestCase):
    def test_priority_source_readiness_is_complete(self) -> None:
        report = build_readiness(ROOT)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["priority_sources"], len(PRIORITY_SOURCE_IDS))
        self.assertGreaterEqual(report["priority_sources"], 20)

    def test_every_mart_has_explicit_dependencies(self) -> None:
        expected = {
            "climate_rollups",
            "storage_balance",
            "freight_lanes",
            "fertilizer_imports",
            "biomass",
            "hydrology_latest",
            "ptax_current",
            "imea_freight_reference",
            "overview_current",
        }
        self.assertEqual(set(SOURCE_DEPENDENCIES), expected)
        self.assertTrue(all(SOURCE_DEPENDENCIES[key] for key in expected))


if __name__ == "__main__":
    unittest.main()
