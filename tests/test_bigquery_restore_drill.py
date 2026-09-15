from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.run_bigquery_restore_drill import field_signature, safe_identifier


class BigQueryRestoreDrillTests(unittest.TestCase):
    def test_safe_identifier_accepts_expected_gcp_identifiers(self) -> None:
        self.assertEqual(safe_identifier("agrolog-mt-prod", "project"), "agrolog-mt-prod")
        self.assertEqual(safe_identifier("agrolog_ops", "dataset"), "agrolog_ops")
        self.assertEqual(safe_identifier("collector_runs", "table"), "collector_runs")

    def test_safe_identifier_rejects_sql_or_qualified_input(self) -> None:
        for value in (
            "agrolog_ops.collector_runs",
            "`agrolog_ops`",
            "x;DROP TABLE y",
            "x y",
            "",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    safe_identifier(value, "identifier")

    def test_field_signature_preserves_schema_identity(self) -> None:
        fields = [
            SimpleNamespace(name="source_id", field_type="STRING", mode="REQUIRED"),
            SimpleNamespace(name="inserted_at", field_type="TIMESTAMP", mode="NULLABLE"),
        ]
        self.assertEqual(
            field_signature(fields),
            [("source_id", "STRING", "REQUIRED"), ("inserted_at", "TIMESTAMP", "NULLABLE")],
        )


if __name__ == "__main__":
    unittest.main()
