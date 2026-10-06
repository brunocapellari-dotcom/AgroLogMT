from __future__ import annotations

import json
import unittest

from collector.ibge_ppm import build_canonical_rows, dataset_url, parse_payload


class IbgePpmCollectorTests(unittest.TestCase):
    def _payload(self) -> bytes:
        return json.dumps(
            [
                {
                    "D1N": "Município",
                    "D2N": "Variável",
                    "D3N": "Ano",
                    "D4N": "Tipo de rebanho",
                    "V": "Valor",
                },
                {
                    "D1C": "5105259",
                    "D1N": "Lucas do Rio Verde (MT)",
                    "D2N": "Efetivo dos rebanhos",
                    "D3N": "2023",
                    "D4N": "Bovino",
                    "V": "150000",
                },
                {
                    "D1C": "5105259",
                    "D1N": "Lucas do Rio Verde (MT)",
                    "D2N": "Efetivo dos rebanhos",
                    "D3N": "2024",
                    "D4N": "Bovino",
                    "V": "160.000",
                },
                {
                    "D1C": "5103403",
                    "D1N": "Cuiabá (MT)",
                    "D2N": "Efetivo dos rebanhos",
                    "D3N": "2024",
                    "D4N": "Bubalino",
                    "V": "999",
                },
            ],
            ensure_ascii=False,
        ).encode("utf-8")

    def test_dataset_url_scopes_municipalities_inside_mt(self) -> None:
        url = dataset_url(period=2024)
        self.assertIn("/t/3939/", url)
        self.assertIn("/n6/in%20n3%2051/", url)
        self.assertIn("/v/105/p/2024/c79/2670", url)

    def test_parse_payload_filters_bovine_herd_and_parses_thousands(self) -> None:
        rows = parse_payload(self._payload())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["year"], 2024)
        self.assertEqual(rows[1]["cattle_head"], 160000.0)

    def test_canonical_rows_preserve_point_in_time_boundary(self) -> None:
        rows, stats = build_canonical_rows(
            self._payload(),
            source_url="https://apisidra.ibge.gov.br/example",
            data_coleta="2026-09-15T12:00:00+00:00",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(stats["municipalities"], 1)
        self.assertEqual(stats["year_min"], 2023)
        self.assertEqual(stats["year_max"], 2024)
        for row in rows:
            self.assertEqual(row["unit"], "cabecas")
            self.assertEqual(row["metric_id"], "pecuaria.rebanho_bovino")
            self.assertTrue(row["data_referencia"].endswith("-12-31"))
            self.assertIsNone(row["data_publicacao"])
            self.assertFalse(row["availability_verified"])
            self.assertFalse(row["point_in_time_feature_eligible"])
            self.assertEqual(row["evidence_class"], "observado")

    def test_record_ids_are_stable_across_collection_times(self) -> None:
        first, _ = build_canonical_rows(
            self._payload(), source_url="x", data_coleta="2026-09-15T10:00:00+00:00"
        )
        second, _ = build_canonical_rows(
            self._payload(), source_url="x", data_coleta="2026-09-16T10:00:00+00:00"
        )
        self.assertEqual([row["record_id"] for row in first], [row["record_id"] for row in second])

    def test_duplicate_municipality_year_is_rejected(self) -> None:
        decoded = json.loads(self._payload().decode("utf-8"))
        decoded.append(decoded[1])
        with self.assertRaisesRegex(ValueError, "duplicado"):
            parse_payload(json.dumps(decoded, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
