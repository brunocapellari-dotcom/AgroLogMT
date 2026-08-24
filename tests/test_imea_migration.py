from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from collector.imea_migration import TABLE_SPECS, cotton_yield_arroba_to_kg_ha, validate_bundle, validate_csv


class ImeaMigrationTests(unittest.TestCase):
    def _write(self, path: Path, header: tuple[str, ...], rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(header))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in header})

    def test_trusted_indicator_passes_with_unique_hash_and_ok_qa(self) -> None:
        spec = TABLE_SPECS["indicadores"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "indicadores.csv"
            row = {column: "x" for column in spec.required_columns}
            row.update({"hash_registro": "h1", "qa_status": "OK", "source_file": "imea.xls"})
            self._write(path, spec.required_columns, [row])
            result = validate_csv(path, spec)
            self.assertEqual(result.status, "pass")
            self.assertEqual(result.rows, 1)
            self.assertEqual(result.unique_merge_keys, 1)

    def test_trusted_indicator_blocks_ambiguous_qa(self) -> None:
        spec = TABLE_SPECS["indicadores"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "indicadores.csv"
            row = {column: "x" for column in spec.required_columns}
            row.update({"hash_registro": "h1", "qa_status": "AMBIGUO", "source_file": "imea.xls"})
            self._write(path, spec.required_columns, [row])
            result = validate_csv(path, spec)
            self.assertEqual(result.status, "blocked_trusted_qa")
            self.assertEqual(result.qa_blocked_rows, 1)

    def test_duplicate_merge_key_is_never_silently_deduplicated(self) -> None:
        spec = TABLE_SPECS["custos"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custos.csv"
            row = {column: "x" for column in spec.required_columns}
            row.update({"hash_registro": "same", "source_file": "custos.xls"})
            self._write(path, spec.required_columns, [row, row])
            result = validate_csv(path, spec)
            self.assertEqual(result.status, "blocked_duplicate_merge_key")
            self.assertEqual(result.duplicate_merge_keys, 1)

    def test_missing_column_fails_closed(self) -> None:
        spec = TABLE_SPECS["od"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "od.csv"
            header = tuple(column for column in spec.required_columns if column != "data_publicacao")
            self._write(path, header, [])
            with self.assertRaises(ValueError):
                validate_csv(path, spec)

    def test_bundle_reports_missing_groups_instead_of_inventing_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_bundle(tmp, require_all=True)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(set(result["missing_groups"]), set(TABLE_SPECS))

    def test_cotton_arroba_conversion_preserves_audited_factor(self) -> None:
        self.assertEqual(cotton_yield_arroba_to_kg_ha(100.0), 1500.0)


if __name__ == "__main__":
    unittest.main()
