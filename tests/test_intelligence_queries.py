from __future__ import annotations

import unittest

from gateway.intelligence_queries import (
    build_biomass_sql,
    build_fertilizer_imports_sql,
    build_freight_lanes_sql,
    build_hydrology_latest_sql,
    build_imea_freight_reference_sql,
    build_overview_sql,
    build_ptax_current_sql,
    build_storage_balance_sql,
)


class IntelligenceQueriesTests(unittest.TestCase):
    def test_queries_target_canonical_marts(self) -> None:
        builders = (
            build_overview_sql,
            build_storage_balance_sql,
            build_freight_lanes_sql,
            build_fertilizer_imports_sql,
            build_biomass_sql,
            build_hydrology_latest_sql,
            build_ptax_current_sql,
            build_imea_freight_reference_sql,
        )
        for builder in builders:
            sql = builder("agrolog-prod", "marts_agrolog360")
            self.assertIn("marts_agrolog360", sql)
            self.assertIn("agrolog-prod", sql)

    def test_identifier_injection_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_overview_sql("bad project", "marts_agrolog360")


if __name__ == "__main__":
    unittest.main()
