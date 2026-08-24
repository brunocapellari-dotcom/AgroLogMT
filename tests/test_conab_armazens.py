from __future__ import annotations

import unittest

from collector.conab_armazens import parse_conab_armazens


class ConabArmazensParserTests(unittest.TestCase):
    def test_brazilian_semicolon_snapshot(self) -> None:
        payload = (
            "CDA;CNPJ;Razão Social;Nome Armazém;Município;UF;Tipo Estrutura;Capacidade Estática;Latitude;Longitude\n"
            "12345;00111222000133;Armazéns Teste SA;Unidade Norte;Lucas do Rio Verde;MT;Graneleiro;12.345,50;-13,05;-55,91\n"
            "12346;00444555000166;Outro Armazém SA;Unidade Sul;Sorriso;MT;Silo;8.000;-12,54;-55,72\n"
        ).encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="abc123", data_coleta="2026-08-24T15:00:00+00:00",
            raw_artifact_ref="drive://fixture", observed_url="https://example.test/armazens.txt",
            collector_version="test",
        )
        self.assertEqual(parsed.records_read, 2)
        self.assertEqual(parsed.records_accepted, 2)
        self.assertEqual(parsed.rows[0]["municipio"], "Lucas do Rio Verde")
        self.assertEqual(parsed.rows[0]["uf"], "MT")
        self.assertAlmostEqual(parsed.rows[0]["capacidade_estatica_t"], 12345.5)
        self.assertAlmostEqual(parsed.rows[1]["capacidade_estatica_t"], 8000.0)
        self.assertEqual(parsed.rows[0]["warehouse_id"], "cda:12345")
        self.assertEqual(parsed.rows[0]["evidence_class"], "observado")

    def test_duplicate_rows_are_removed_within_snapshot(self) -> None:
        payload = "CDA|Municipio|UF|Capacidade\n1|Sorriso|MT|1000\n1|Sorriso|MT|1000\n".encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="hash", data_coleta="2026-08-24T15:00:00+00:00",
            raw_artifact_ref=None, observed_url=None,
        )
        self.assertEqual(parsed.records_read, 2)
        self.assertEqual(parsed.records_accepted, 1)
        self.assertEqual(parsed.duplicates_removed, 1)

    def test_unknown_columns_are_preserved(self) -> None:
        payload = "CDA;Municipio;UF;Capacidade;Campo Novo\n9;Sinop;MT;2500;X\n".encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="hash2", data_coleta="2026-08-24T15:00:00+00:00",
            raw_artifact_ref=None, observed_url=None,
        )
        self.assertIn("Campo Novo", parsed.rows[0]["source_payload_json"])


if __name__ == "__main__":
    unittest.main()
