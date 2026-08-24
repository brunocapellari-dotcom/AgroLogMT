from __future__ import annotations

import unittest

from scripts.inventory_conab_history import filter_range
from scripts.merge_conab_inventories import merge_reports


class ConabDeepRegistryTests(unittest.TestCase):
    def test_inventory_filter_is_range_pure(self) -> None:
        plan = [
            {"safra": "2011/12", "levantamento": 1},
            {"safra": "2025/26", "levantamento": 1},
            {"safra": None, "levantamento": 2},
        ]
        filtered = filter_range(plan, 2010, 2013)
        self.assertEqual([(x["safra"], x["levantamento"]) for x in filtered], [("2011/12", 1)])

    def test_registry_prefers_verified_direct_then_nested(self) -> None:
        blocked = {"safra":"2022/23","levantamento":3,"execution_status":"blocked_suspected_site_migration_timestamp","availability_verified":False,"availability_basis":None,"data_publicacao":"2025-01-01T00:00:00+00:00"}
        nested = {"safra":"2022/23","levantamento":3,"execution_status":"ready","availability_verified":True,"availability_basis":"official_nested_page_timestamp","data_publicacao":"2022-12-10T12:00:00+00:00"}
        direct = {"safra":"2022/23","levantamento":3,"execution_status":"ready","availability_verified":True,"availability_basis":"official_page_timestamp","data_publicacao":"2022-12-10T12:00:00+00:00"}
        registry = merge_reports([
            {"range":{"start_year":2022,"end_year":2022},"items":[blocked,nested]},
            {"range":{"start_year":2022,"end_year":2022},"items":[direct]},
        ])
        self.assertEqual(registry["summary"]["vintages"], 1)
        self.assertEqual(registry["summary"]["ready"], 1)
        self.assertEqual(registry["items"][0]["availability_basis"], "official_page_timestamp")


if __name__ == "__main__":
    unittest.main()
