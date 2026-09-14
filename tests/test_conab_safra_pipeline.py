from __future__ import annotations

import unittest
from unittest.mock import patch

from collector.conab_safra import ConabSafraRecord
from collector.conab_safra_bigquery import ConabSafraBigQueryLoader, _expected_snapshot_records
from collector.conab_safra_pipeline import build_canonical_rows


class ConabSafraPipelineTests(unittest.TestCase):
    def _record(self) -> ConabSafraRecord:
        return ConabSafraRecord(
            source_id="conab_safra_graos_xlsx",
            geo_level="uf",
            geo_id="MT",
            produto_origem="SOJA",
            product_id="soja",
            safra="25/26",
            vintage_position="current",
            area_mil_ha=13006.2,
            produtividade_kg_ha=3969.0,
            producao_mil_t=51621.6,
            area_var_pct=2.1,
            produtividade_var_pct=-1.5,
            producao_var_pct=0.6,
            identity_error_mil_t=0.01,
            identity_error_pct=0.001,
            quality_score=1.0,
            quality_flags=(),
            source_sheet="MT",
            source_row=36,
        )

    @patch("collector.conab_safra_pipeline.parse_conab_safra_workbook")
    def test_builds_canonical_point_in_time_metadata(self, parse) -> None:
        parse.return_value = [self._record()]
        rows, stats = build_canonical_rows(
            b"fixture",
            snapshot_id="abc123",
            data_coleta="2026-08-24T18:00:00+00:00",
            raw_artifact_ref="drive://raw/conab.xlsx",
            observed_url="https://www.gov.br/conab/file.xlsx/@@download/file",
            last_modified="Thu, 13 Aug 2026 12:00:00 GMT",
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["snapshot_id"], "abc123")
        self.assertEqual(row["data_referencia"], "2026-08-13")
        self.assertEqual(row["competencia"], "2026-08")
        self.assertEqual(row["evidence_class"], "estimado")
        self.assertEqual(row["source_hash"], "abc123")
        self.assertEqual(row["raw_artifact_ref"], "drive://raw/conab.xlsx")
        self.assertEqual(stats["data_publicacao_basis"], "http_last_modified")
        self.assertEqual(stats["current_quality_flagged"], 0)

    @patch("collector.conab_safra_pipeline.parse_conab_safra_workbook")
    def test_record_id_is_stable_for_same_snapshot_and_natural_key(self, parse) -> None:
        parse.return_value = [self._record()]
        kwargs = dict(
            payload=b"fixture",
            snapshot_id="abc123",
            data_coleta="2026-08-24T18:00:00+00:00",
            raw_artifact_ref=None,
            observed_url=None,
            last_modified=None,
        )
        first, _ = build_canonical_rows(**kwargs)
        second, _ = build_canonical_rows(**kwargs)
        self.assertEqual(first[0]["record_id"], second[0]["record_id"])

    def test_expected_snapshot_records_counts_exact_duplicate_ids(self) -> None:
        rows = [
            {"snapshot_id": "snap", "record_id": "a"},
            {"snapshot_id": "snap", "record_id": "a"},
            {"snapshot_id": "snap", "record_id": "b"},
        ]
        expected, duplicates = _expected_snapshot_records(rows, "snap")
        self.assertEqual(expected, 2)
        self.assertEqual(duplicates, 1)

    def test_expected_snapshot_records_rejects_mixed_snapshot(self) -> None:
        with self.assertRaises(ValueError):
            _expected_snapshot_records(
                [
                    {"snapshot_id": "snap", "record_id": "a"},
                    {"snapshot_id": "other", "record_id": "b"},
                ],
                "snap",
            )

    def test_snapshot_tie_out_fails_closed(self) -> None:
        ConabSafraBigQueryLoader._assert_snapshot_count(2, 2, snapshot_id="snap")
        with self.assertRaises(RuntimeError):
            ConabSafraBigQueryLoader._assert_snapshot_count(2, 1, snapshot_id="snap")


if __name__ == "__main__":
    unittest.main()
