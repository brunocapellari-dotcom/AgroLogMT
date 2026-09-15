from __future__ import annotations

import unittest

from collector.nass_quickstats_bigquery import _expected_snapshot_records
from collector.nass_quickstats_normalizer import (
    nass_record_id,
    normalize_nass_rows,
    parse_nass_value,
    validate_normalized_nass_rows,
)


BASE_ROW = {
    "source_desc": "SURVEY",
    "sector_desc": "CROPS",
    "group_desc": "FIELD CROPS",
    "commodity_desc": "CORN",
    "class_desc": "ALL CLASSES",
    "util_practice_desc": "GRAIN",
    "prodn_practice_desc": "ALL PRODUCTION PRACTICES",
    "statisticcat_desc": "PROGRESS",
    "unit_desc": "PCT PLANTED",
    "short_desc": "CORN - PROGRESS, MEASURED IN PCT PLANTED",
    "domain_desc": "TOTAL",
    "domaincat_desc": "NOT SPECIFIED",
    "agg_level_desc": "STATE",
    "state_ansi": "19",
    "state_alpha": "IA",
    "state_name": "IOWA",
    "asd_code": "",
    "asd_desc": "",
    "county_ansi": "",
    "county_name": "",
    "region_desc": "",
    "zip_5": "",
    "watershed_code": "00000000",
    "watershed_desc": "",
    "congr_district_code": "",
    "country_code": "9000",
    "country_name": "UNITED STATES",
    "year": "2026",
    "freq_desc": "WEEKLY",
    "begin_code": "00",
    "end_code": "00",
    "reference_period_desc": "WEEK #20",
    "week_ending": "2026-05-17",
    "load_time": "2026-05-18 16:00:00",
    "Value": "91",
}


class NassNormalizerTests(unittest.TestCase):
    def test_numeric_and_suppression_values_are_not_conflated(self) -> None:
        value, suppression, raw = parse_nass_value("1,234.5")
        self.assertEqual(value, 1234.5)
        self.assertIsNone(suppression)
        self.assertEqual(raw, "1,234.5")

        value, suppression, raw = parse_nass_value("(D)")
        self.assertIsNone(value)
        self.assertEqual(suppression, "(D)")
        self.assertEqual(raw, "(D)")

    def test_record_id_is_stable_across_value_and_load_time_revision(self) -> None:
        first = dict(BASE_ROW)
        revised = dict(BASE_ROW, Value="93", load_time="2026-05-19 09:00:00")
        self.assertEqual(nass_record_id(first), nass_record_id(revised))

    def test_normalization_preserves_source_load_time_without_claiming_publication(self) -> None:
        rows = normalize_nass_rows(
            [BASE_ROW],
            source_id="usda_nass_corn_weekly_current",
            snapshot_id="snapshot-a",
            data_coleta="2026-05-18T20:00:00+00:00",
            source_url="https://quickstats.nass.usda.gov/api/api_GET/?key=%5BREDACTED%5D",
            source_hash="hash-a",
            raw_artifact_ref="drive://raw-a",
        )
        row = rows[0]
        self.assertEqual(row["data_referencia"], "2026-05-17")
        self.assertIsNone(row["data_publicacao"])
        self.assertEqual(row["source_load_time"], "2026-05-18 16:00:00")
        self.assertEqual(row["value_numeric"], 91.0)
        self.assertEqual(row["evidence_class"], "observado")

    def test_quality_gate_requires_expected_commodity_frequency_and_valid_week_date(self) -> None:
        rows = normalize_nass_rows(
            [BASE_ROW],
            source_id="source-a",
            snapshot_id="snapshot-a",
            data_coleta="2026-05-18T20:00:00+00:00",
            source_url="https://example.org",
            source_hash="hash-a",
            raw_artifact_ref=None,
        )
        quality = validate_normalized_nass_rows(
            rows,
            expected_source_id="source-a",
            expected_commodity="CORN",
            expected_frequency="WEEKLY",
        )
        self.assertEqual(quality["status"], "ok")
        self.assertEqual(quality["duplicates"], 0)

        with self.assertRaisesRegex(ValueError, "commodity mismatch"):
            validate_normalized_nass_rows(
                rows,
                expected_source_id="source-a",
                expected_commodity="SOYBEANS",
                expected_frequency="WEEKLY",
            )

        bad = dict(BASE_ROW, week_ending="not-a-date")
        bad_rows = normalize_nass_rows(
            [bad],
            source_id="source-a",
            snapshot_id="snapshot-a",
            data_coleta="2026-05-18T20:00:00+00:00",
            source_url="https://example.org",
            source_hash="hash-a",
            raw_artifact_ref=None,
        )
        with self.assertRaisesRegex(ValueError, "week_ending"):
            validate_normalized_nass_rows(
                bad_rows,
                expected_source_id="source-a",
                expected_commodity="CORN",
                expected_frequency="WEEKLY",
            )

    def test_bigquery_expected_records_counts_duplicates_and_rejects_mixed_snapshot(self) -> None:
        expected, duplicates = _expected_snapshot_records(
            [
                {"snapshot_id": "snap", "record_id": "a"},
                {"snapshot_id": "snap", "record_id": "a"},
                {"snapshot_id": "snap", "record_id": "b"},
            ],
            "snap",
        )
        self.assertEqual(expected, 2)
        self.assertEqual(duplicates, 1)

        with self.assertRaises(ValueError):
            _expected_snapshot_records(
                [
                    {"snapshot_id": "snap", "record_id": "a"},
                    {"snapshot_id": "other", "record_id": "b"},
                ],
                "snap",
            )


if __name__ == "__main__":
    unittest.main()
