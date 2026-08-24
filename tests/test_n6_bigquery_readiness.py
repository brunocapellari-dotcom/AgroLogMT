from __future__ import annotations

import unittest

from scripts.inspect_n6_bigquery_readiness import (
    build_history_query,
    infer_schema_readiness,
    required_tables,
    split_table_name,
)


class BigQueryReadinessTests(unittest.TestCase):
    def test_split_table_name_rejects_unsafe_identifiers(self) -> None:
        self.assertEqual(split_table_name("agro.conab_safra"), ("agro", "conab_safra"))
        with self.assertRaises(ValueError):
            split_table_name("agro.table;DROP")
        with self.assertRaises(ValueError):
            split_table_name("project.agro.table")

    def test_schema_inference_is_conservative(self) -> None:
        ready = infer_schema_readiness({"data_coleta", "data_publicacao", "geo_id"})
        self.assertTrue(ready["point_in_time_ready"])
        self.assertTrue(ready["canonical_geo_ready"])

        incomplete = infer_schema_readiness({"data_referencia", "municipio"})
        self.assertFalse(incomplete["point_in_time_ready"])
        self.assertFalse(incomplete["canonical_geo_ready"])

    def test_history_query_uses_known_fields_only(self) -> None:
        query = build_history_query(
            "project-x",
            "agro.conab_safra",
            {"data_referencia", "safra", "snapshot_id"},
        )
        self.assertIsNotNone(query)
        self.assertIn("COUNT(DISTINCT CAST(safra AS STRING))", query)
        self.assertIn("COUNT(DISTINCT CAST(snapshot_id AS STRING))", query)
        self.assertIn("`project-x.agro.conab_safra`", query)

    def test_required_tables_deduplicates_contract_sources(self) -> None:
        contract = {
            "blocks": [
                {"tables_all": ["a.one", "b.two"]},
                {"tables_any": ["b.two", "c.three"]},
            ]
        }
        self.assertEqual(required_tables(contract), ["a.one", "b.two", "c.three"])


if __name__ == "__main__":
    unittest.main()
