from __future__ import annotations

import unittest

from gateway.storage_queries import build_latest_summary_sql, normalize_limit, normalize_uf, safe_identifier


class StorageQueryTests(unittest.TestCase):
    def test_query_uses_parameters_for_user_filters(self) -> None:
        sql = build_latest_summary_sql("agrolog-prod", "logistica")
        self.assertIn("@uf", sql)
        self.assertIn("@municipio", sql)
        self.assertNotIn("Lucas do Rio Verde", sql)

    def test_identifier_rejects_sql_injection(self) -> None:
        with self.assertRaises(ValueError):
            safe_identifier("logistica`; DROP TABLE x; --", label="dataset")

    def test_uf_and_limit_validation(self) -> None:
        self.assertEqual(normalize_uf("mt"), "MT")
        self.assertEqual(normalize_limit(100), 100)
        with self.assertRaises(ValueError):
            normalize_uf("MTO")
        with self.assertRaises(ValueError):
            normalize_limit(1001)


if __name__ == "__main__":
    unittest.main()
