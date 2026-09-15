from __future__ import annotations

import json
import unittest

from collector.ibge_slaughter import build_canonical_rows, dataset_path, parse_payload


class IbgeSlaughterCollectorTests(unittest.TestCase):
    def _payload(self) -> bytes:
        return json.dumps(
            [
                {
                    "D1N": "Unidade da Federação",
                    "D2N": "Variável",
                    "D3N": "Trimestre",
                    "D4N": "Referência temporal",
                    "D5N": "Tipo de inspeção",
                    "D6N": "Tipo de rebanho bovino",
                    "V": "Valor",
                },
                {
                    "D1C": "51",
                    "D1N": "Mato Grosso",
                    "D2C": "284",
                    "D2N": "Animais abatidos",
                    "D3C": "202401",
                    "D3N": "1º trimestre 2024",
                    "D4C": "115236",
                    "D4N": "Total do trimestre",
                    "D5C": "118225",
                    "D5N": "Total",
                    "D6C": "992",
                    "D6N": "Total",
                    "V": "1.234.000",
                },
                {
                    "D1C": "51",
                    "D1N": "Mato Grosso",
                    "D2C": "285",
                    "D2N": "Peso total das carcaças",
                    "D3C": "202401",
                    "D3N": "1º trimestre 2024",
                    "D4C": "115236",
                    "D4N": "Total do trimestre",
                    "D5C": "118225",
                    "D5N": "Total",
                    "D6C": "992",
                    "D6N": "Total",
                    "V": "321000000",
                },
                {
                    "D1C": "52",
                    "D1N": "Goiás",
                    "D2C": "284",
                    "D2N": "Animais abatidos",
                    "D3C": "202401",
                    "D3N": "1º trimestre 2024",
                    "D4C": "115236",
                    "D4N": "Total do trimestre",
                    "D5C": "118225",
                    "D5N": "Total",
                    "D6C": "992",
                    "D6N": "Total",
                    "V": "999",
                },
            ],
            ensure_ascii=False,
        ).encode("utf-8")

    def test_dataset_path_locks_total_quarter_inspection_and_cattle(self) -> None:
        path = dataset_path(period="202401")
        self.assertIn("t/1092/n3/51/v/284,285/p/202401", path)
        self.assertIn("/c12716/115236", path)
        self.assertIn("/c12529/118225", path)
        self.assertIn("/c18/992", path)

    def test_parse_payload_returns_two_mt_metrics(self) -> None:
        rows = parse_payload(self._payload())
        self.assertEqual(len(rows), 2)
        by_metric = {row["metric_id"]: row for row in rows}
        self.assertEqual(by_metric["pecuaria.abate_bovino_cabecas"]["value"], 1234000.0)
        self.assertEqual(by_metric["pecuaria.abate_bovino_peso_carcaca"]["value"], 321000000.0)
        self.assertEqual({row["quarter"] for row in rows}, {1})

    def test_canonical_rows_preserve_revision_and_point_in_time_boundary(self) -> None:
        rows, stats = build_canonical_rows(
            self._payload(),
            source_url="https://apisidra.ibge.gov.br/example",
            data_coleta="2026-09-15T16:00:00+00:00",
        )
        self.assertEqual(stats["quarters"], 1)
        self.assertEqual(stats["year_min"], 2024)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["competencia"], "2024-Q1")
            self.assertEqual(row["data_referencia"], "2024-03-31")
            self.assertIsNone(row["data_publicacao"])
            self.assertFalse(row["availability_verified"])
            self.assertFalse(row["point_in_time_feature_eligible"])
            self.assertEqual(row["evidence_class"], "observado")

    def test_record_ids_are_stable_across_collection_times(self) -> None:
        first, _ = build_canonical_rows(self._payload(), source_url="x", data_coleta="2026-09-15T10:00:00+00:00")
        second, _ = build_canonical_rows(self._payload(), source_url="x", data_coleta="2026-09-16T10:00:00+00:00")
        self.assertEqual([row["record_id"] for row in first], [row["record_id"] for row in second])


if __name__ == "__main__":
    unittest.main()
