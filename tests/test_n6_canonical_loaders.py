from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from collector.comexstat_bigquery import canonical_row, write_ndjson
from collector.geo_ibge import Municipality
from collector.geo_ibge_bigquery import municipality_record_id, municipality_rows
from collector.nasa_power import PowerObservation
from collector.nasa_power_bigquery import power_record_id, power_rows


class CanonicalLoadersTests(unittest.TestCase):
    def test_ibge_record_id_is_content_deterministic(self) -> None:
        row = Municipality(
            codigo_ibge=5105259, municipio="Lucas do Rio Verde", uf="MT", uf_codigo_ibge=51,
            mesorregiao="Norte Mato-grossense", microrregiao="Alto Teles Pires",
            regiao_imediata="Sorriso", regiao_intermediaria="Sinop",
        )
        self.assertEqual(municipality_record_id(row), municipality_record_id(row))
        payload = municipality_rows(
            [row], snapshot_id="snap", data_coleta="2026-08-24T12:00:00Z",
            source_url="https://ibge", source_hash="hash", raw_artifact_ref="drive://x",
        )[0]
        self.assertEqual(payload["codigo_ibge"], 5105259)
        self.assertEqual(payload["evidence_class"], "observado")

    def test_nasa_power_keeps_modelled_evidence_subtype(self) -> None:
        row = PowerObservation(
            date="2025-01-01", latitude=-13.05, longitude=-55.91,
            parameter="PRECTOTCORR", value=10.2, unit="mm/day",
        )
        self.assertEqual(power_record_id(row), power_record_id(row))
        payload = power_rows(
            [row], snapshot_id="snap", data_coleta="2026-08-24T12:00:00Z",
            source_url="https://power", source_hash="hash", raw_artifact_ref="drive://x",
        )[0]
        self.assertEqual(payload["evidence_class"], "estimado")
        self.assertEqual(payload["evidence_subtype"], "nasa_power_gridded")

    def test_comex_ncm_semantics_never_call_urf_a_port(self) -> None:
        raw = {
            "CO_ANO": 2026, "CO_MES": 7, "CO_NCM": "12019000", "CO_UNID": 10,
            "CO_PAIS": 160, "SG_UF_NCM": "MT", "CO_VIA": 1, "CO_URF": 817600,
            "QT_ESTAT": 100.0, "KG_LIQUIDO": 250000.0, "VL_FOB": 100000.0,
            "toneladas": 250.0, "usd_por_t": 400.0,
        }
        row = canonical_row(
            "ncm_export", raw, snapshot_id="snap", data_coleta="2026-08-24T12:00:00Z",
            data_publicacao=None, source_url="https://mdic", source_hash="hash", raw_artifact_ref="drive://x",
        )
        self.assertEqual(row["geo_semantics"], "uf_produto_origem_destino")
        self.assertEqual(row["urf_semantics"], "unidade_receita_federal_nao_porto_fisico")
        self.assertNotIn("porto", {"co_urf": row["co_urf"]})

    def test_comex_municipality_semantics_are_fiscal_domicile(self) -> None:
        raw = {
            "CO_ANO": 2026, "CO_MES": 7, "SH4": "1201", "CO_PAIS": 160,
            "SG_UF_MUN": "MT", "CO_MUN": 5105259, "KG_LIQUIDO": 1000.0, "VL_FOB": 500.0,
            "toneladas": 1.0, "usd_por_t": 500.0,
        }
        row = canonical_row(
            "municipio_sh4_export", raw, snapshot_id="snap", data_coleta="2026-08-24T12:00:00Z",
            data_publicacao=None, source_url="https://mdic", source_hash="hash", raw_artifact_ref=None,
        )
        self.assertEqual(row["geo_semantics"], "domicilio_fiscal_declarante")
        self.assertIsNone(row["urf_semantics"])

    def test_comex_ndjson_normalization_reports_exact_duplicates(self) -> None:
        csv_text = (
            "CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB\n"
            "2026;7;12019000;10;160;MT;1;817600;100;250000;100000\n"
            "2026;7;12019000;10;160;MT;1;817600;100;250000;100000\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "exp.csv"
            dest = Path(tmp) / "exp.ndjson"
            source.write_text(csv_text, encoding="utf-8")
            result = write_ndjson(
                source, dest, "ncm_export", snapshot_id="snap", data_coleta="2026-08-24T12:00:00Z",
                data_publicacao=None, source_url="https://mdic", source_hash="hash", raw_artifact_ref="drive://x",
            )
            self.assertEqual(result["rows"], 2)
            self.assertEqual(result["unique_record_ids"], 1)
            self.assertEqual(result["exact_duplicate_rows"], 1)
            self.assertEqual(len(dest.read_text(encoding="utf-8").splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
