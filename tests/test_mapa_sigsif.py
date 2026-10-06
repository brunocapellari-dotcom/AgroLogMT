from __future__ import annotations

import unittest

from collector.mapa_sigsif import FEMALE_METRIC, MALE_METRIC, build_canonical_rows, parse_payload
from collector.mapa_sigsif_bigquery import MapaSigsifBigQueryLoader


class MapaSigsifTests(unittest.TestCase):
    def _payload(self) -> bytes:
        return (
            "UF - PROCEDÊNCIA;CATEGORIA;MACHO;FÊMEA\n"
            "MT;BOVINOS;120000;80000\n"
            "MT;SUÍNOS;500;600\n"
            "GO;BOVINOS;999;888\n"
        ).encode("utf-8")

    def test_parser_filters_mt_bovines_and_sex_counts(self) -> None:
        parsed = parse_payload(self._payload())
        self.assertEqual(parsed["uf"], "MT")
        self.assertEqual(parsed["male"], 120000)
        self.assertEqual(parsed["female"], 80000)

    def test_canonical_rows_are_snapshot_crosscheck_not_historical_flow(self) -> None:
        rows, stats = build_canonical_rows(
            self._payload(),
            source_url="https://dados.agricultura.gov.br/example.csv",
            data_coleta="2026-09-15T15:00:00+00:00",
        )
        self.assertEqual(stats["total"], 200000)
        self.assertFalse(stats["internal_reference_period_available"])
        self.assertEqual({row["metric_id"] for row in rows}, {MALE_METRIC, FEMALE_METRIC})
        for row in rows:
            self.assertEqual(row["snapshot_date"], "2026-09-15")
            self.assertTrue(row["availability_verified"])
            self.assertFalse(row["point_in_time_feature_eligible"])
            self.assertEqual(row["target_role"], "current_sif_crosscheck_not_historical_flow")
            self.assertIn("no_internal_reference_period", row["quality_flags"])

    def test_loader_contract_rejects_temporal_promotion(self) -> None:
        rows, _ = build_canonical_rows(
            self._payload(), source_url="x", data_coleta="2026-09-15T15:00:00+00:00"
        )
        MapaSigsifBigQueryLoader._validate_rows(rows, rows[0]["snapshot_id"])
        rows[0]["point_in_time_feature_eligible"] = True
        with self.assertRaisesRegex(ValueError, "point-in-time"):
            MapaSigsifBigQueryLoader._validate_rows(rows, rows[0]["snapshot_id"])

    def test_duplicate_bovine_mt_rows_fail_closed(self) -> None:
        payload = self._payload().decode("utf-8") + "MT;BOVINOS;1;1\n"
        with self.assertRaisesRegex(ValueError, "exatamente 1"):
            parse_payload(payload.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
