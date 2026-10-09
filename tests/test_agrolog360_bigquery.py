from __future__ import annotations

import unittest

from collector.agrolog360_bigquery import AgroLog360BigQueryLoader, stable_record_id, table_ddl


class AgroLog360BigQueryTests(unittest.TestCase):
    def test_ddl_is_partitioned_and_clustered(self) -> None:
        for kind in ("climate", "freight", "biomass"):
            dataset_sql, table_sql = table_ddl("agrolog-prod", kind)
            self.assertIn("CREATE SCHEMA IF NOT EXISTS", dataset_sql)
            self.assertIn("PARTITION BY data_referencia", table_sql)
            self.assertIn("CLUSTER BY", table_sql)

    def test_every_table_has_explicit_merge_columns(self) -> None:
        from collector.agrolog360_bigquery import TABLES
        for kind, spec in TABLES.items():
            self.assertIn("columns", spec, kind)
            self.assertEqual(spec["columns"][0], "record_id")
            self.assertEqual(len(spec["columns"]), len(set(spec["columns"])))

    def test_stable_record_id_is_deterministic(self) -> None:
        self.assertEqual(stable_record_id(["a", 1, None]), stable_record_id(["a", 1, None]))
        self.assertNotEqual(stable_record_id(["a", 1]), stable_record_id(["a", 2]))

    def test_empty_load_fails_before_creating_objects(self) -> None:
        loader = object.__new__(AgroLog360BigQueryLoader)
        loader.project_id = "agrolog-prod"
        with self.assertRaisesRegex(ValueError, "carga vazia"):
            loader._prepare("climate", [])

    def test_climate_record_id_is_derived_from_source_geo_date(self) -> None:
        loader = object.__new__(AgroLog360BigQueryLoader)
        rows = loader._prepare("climate", [{
            "source_id": "inmet_weather",
            "geo_id": "MT",
            "data_referencia": "2026-09-29",
        }])
        self.assertEqual(len(rows[0]["record_id"]), 64)


if __name__ == "__main__":
    unittest.main()
