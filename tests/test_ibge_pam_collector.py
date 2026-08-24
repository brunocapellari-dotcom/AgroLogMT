from __future__ import annotations

import json
import unittest

from collector.ibge_pam import build_canonical_rows, parse_payload


class IbgePamCollectorTests(unittest.TestCase):
    def _payload(self) -> bytes:
        return json.dumps([
            {"D1N": "Unidade da Federação", "D2N": "Variável", "D3N": "Ano", "D4N": "Produto", "V": "Valor"},
            {"D1N": "Mato Grosso", "D2N": "Rendimento médio da produção", "D3N": "2022", "D4N": "Soja (em grão)", "V": "3500"},
            {"D1N": "Mato Grosso", "D2N": "Rendimento médio da produção", "D3N": "2023", "D4N": "Soja (em grão)", "V": "3.750"},
            {"D1N": "Goiás", "D2N": "Rendimento médio da produção", "D3N": "2023", "D4N": "Soja (em grão)", "V": "3900"}
        ], ensure_ascii=False).encode("utf-8")

    def test_parse_payload_filters_mt_soy_yield(self) -> None:
        rows = parse_payload(self._payload())
        self.assertEqual([row["year"] for row in rows], [2022, 2023])
        self.assertEqual(rows[1]["yield_kg_ha"], 3750.0)

    def test_canonical_rows_never_claim_historical_publication_time(self) -> None:
        rows, stats = build_canonical_rows(
            self._payload(),
            source_url="https://apisidra.ibge.gov.br/example",
            data_coleta="2026-08-24T22:00:00+00:00",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(stats["year_min"], 2022)
        self.assertEqual(stats["year_max"], 2023)
        for row in rows:
            self.assertIsNone(row["data_publicacao"])
            self.assertFalse(row["availability_verified"])
            self.assertFalse(row["point_in_time_feature_eligible"])
            self.assertEqual(row["target_role"], "realized_label_not_point_in_time_feature")
            self.assertIn("publication_time_not_reconstructed", row["quality_flags"])

    def test_record_ids_are_stable_across_collection_times(self) -> None:
        first, _ = build_canonical_rows(self._payload(), source_url="x", data_coleta="2026-08-24T10:00:00+00:00")
        second, _ = build_canonical_rows(self._payload(), source_url="x", data_coleta="2026-08-25T10:00:00+00:00")
        self.assertEqual([row["record_id"] for row in first], [row["record_id"] for row in second])
        self.assertEqual(first[0]["source_hash"], second[0]["source_hash"])


if __name__ == "__main__":
    unittest.main()
