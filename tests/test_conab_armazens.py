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

    def test_current_portal_layout_is_recognized(self) -> None:
        payload = (
            "identificacao_armazem;dsc_especie_armazem;dsc_tipo_armazem;dsc_tipo_entidade;dsc_tipo_pessoa;"
            "nom_municipio;cod_ibge;uf;qtd_capacidade_estatica(t);qtd_capacidade_expedicao(t);"
            "qtd_capacidade_recepcao(t);latitude;longitude;nome_armazenador;endereco;email\n"
            "56.0000.0034-0;GRANEL SÓLIDO;GRANELEIRO;PRIVADA;PESSOA FÍSICA;ALTO GARÇAS-MT;5100409;MT;"
            "4580,0;50;30;-16.5052;-53.5048;ODILIO BALBINOTTI;ROD. BR 364 KM 94;teste@example.com\n"
        ).encode("latin-1")
        parsed = parse_conab_armazens(
            payload, snapshot_id="live-layout", data_coleta="2026-08-24T20:45:00+00:00",
            raw_artifact_ref=None, observed_url="https://portaldeinformacoes.conab.gov.br/fixture",
        )
        row = parsed.rows[0]
        self.assertEqual(row["cda"], "56.0000.0034-0")
        self.assertEqual(row["warehouse_id"], "cda:56.0000.0034-0")
        self.assertEqual(row["municipio"], "ALTO GARÇAS")
        self.assertEqual(row["codigo_ibge"], "5100409")
        self.assertEqual(row["tipo_armazenagem"], "GRANELEIRO")
        self.assertEqual(row["razao_social"], "ODILIO BALBINOTTI")
        self.assertAlmostEqual(row["capacidade_estatica_t"], 4580.0)
        self.assertEqual(row["quality_flags"], [])
        self.assertEqual(parsed.warnings, [])

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

    def test_invalid_values_are_flagged_without_becoming_valid_data(self) -> None:
        payload = (
            "CDA;Municipio;UF;Capacidade;Latitude;Longitude\n"
            "9;Sinop;MTO;-5;-95;200\n"
        ).encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="quality", data_coleta="2026-08-24T15:00:00+00:00",
            raw_artifact_ref=None, observed_url=None,
        )
        row = parsed.rows[0]
        self.assertIn("invalid_uf", row["quality_flags"])
        self.assertIn("negative_capacidade", row["quality_flags"])
        self.assertIn("invalid_latitude", row["quality_flags"])
        self.assertIn("invalid_longitude", row["quality_flags"])
        self.assertIsNone(row["latitude"])
        self.assertIsNone(row["longitude"])
        self.assertLess(row["quality_score"], 1.0)

    def test_reference_date_uses_publication_date_when_valid(self) -> None:
        payload = "CDA;Municipio;UF;Capacidade\n9;Sinop;MT;2500\n".encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="published", data_coleta="2026-08-24T15:00:00+00:00",
            data_publicacao="2026-08-20T12:30:00+00:00",
            raw_artifact_ref=None, observed_url=None,
        )
        self.assertEqual(parsed.rows[0]["data_referencia"], "2026-08-20")
        self.assertEqual(parsed.rows[0]["competencia"], "2026-08-20")

    def test_invalid_publication_date_falls_back_to_collection_date(self) -> None:
        payload = "CDA;Municipio;UF;Capacidade\n9;Sinop;MT;2500\n".encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="fallback-date", data_coleta="2026-08-24T15:00:00+00:00",
            data_publicacao="not-a-date",
            raw_artifact_ref=None, observed_url=None,
        )
        self.assertEqual(parsed.rows[0]["data_referencia"], "2026-08-24")
        self.assertEqual(parsed.rows[0]["competencia"], "2026-08-24")

    def test_missing_required_semantic_columns_raise_blocking_warnings(self) -> None:
        payload = "CDA;Campo A;Campo B\n9;X;Y\n".encode("utf-8")
        parsed = parse_conab_armazens(
            payload, snapshot_id="missing-columns", data_coleta="2026-08-24T15:00:00+00:00",
            raw_artifact_ref=None, observed_url=None,
        )
        self.assertGreaterEqual(len(parsed.warnings), 3)
        self.assertTrue(any("capacidade" in warning for warning in parsed.warnings))
        self.assertTrue(any("municipio" in warning for warning in parsed.warnings))
        self.assertTrue(any("UF" in warning for warning in parsed.warnings))


if __name__ == "__main__":
    unittest.main()
