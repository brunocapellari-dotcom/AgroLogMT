from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from collector.comexstat import chunked, dataset_url, iter_rows, parse_text, validate_header_sample
from collector.comexstat_bigquery import _count_ndjson_records, _count_unique_ndjson_record_ids, write_ndjson


class ComexStatTests(unittest.TestCase):
    def test_ncm_export_preserves_code_and_derives_units(self) -> None:
        text = (
            "CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB\n"
            "2026;7;12019000;10;160;mt;1;817600;100;250000;100000\n"
        )
        row = parse_text(text, "ncm_export")[0]
        self.assertEqual(row["CO_NCM"], "12019000")
        self.assertEqual(row["SG_UF_NCM"], "MT")
        self.assertEqual(row["toneladas"], 250.0)
        self.assertEqual(row["usd_por_t"], 400.0)

    def test_municipio_sh4_keeps_fiscal_geography_semantics(self) -> None:
        text = (
            "CO_ANO;CO_MES;SH4;CO_PAIS;SG_UF_MUN;CO_MUN;KG_LIQUIDO;VL_FOB\n"
            "2026;7;1201;160;MT;5105259;1000;500\n"
        )
        row = parse_text(text, "municipio_sh4_export")[0]
        self.assertEqual(row["SH4"], "1201")
        self.assertEqual(row["CO_MUN"], 5105259)
        self.assertNotIn("CO_URF", row)

    def test_rejects_wrong_layout(self) -> None:
        with self.assertRaises(ValueError):
            list(iter_rows(io.StringIO("CO_ANO;CO_MES\n2026;7\n"), "ncm_export"))

    def test_live_header_validator_accepts_extra_columns(self) -> None:
        sample = (
            b"CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB;EXTRA\n"
            b"2026;7;12019000;10;160;MT;1;817600;100;250000;100000;x\n"
        )
        columns = validate_header_sample(sample, "ncm_export")
        self.assertIn("EXTRA", columns)

    def test_live_header_validator_rejects_missing_required_column(self) -> None:
        sample = b"CO_ANO;CO_MES;CO_NCM\n2026;7;12019000\n"
        with self.assertRaises(ValueError):
            validate_header_sample(sample, "ncm_export")

    def test_chunked_never_requires_full_materialization(self) -> None:
        rows = ({"i": i} for i in range(5))
        batches = list(chunked(rows, size=2))
        self.assertEqual([len(b) for b in batches], [2, 2, 1])

    def test_disk_backed_dedupe_preserves_all_audit_rows(self) -> None:
        header = "CO_ANO;CO_MES;CO_NCM;CO_UNID;CO_PAIS;SG_UF_NCM;CO_VIA;CO_URF;QT_ESTAT;KG_LIQUIDO;VL_FOB\n"
        row = "2026;7;12019000;10;160;MT;1;817600;100;250000;100000\n"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "EXP_2026.csv"
            destination = Path(tmp) / "EXP_2026.ndjson"
            source.write_text(header + row + row, encoding="utf-8")
            stats = write_ndjson(
                source,
                destination,
                "ncm_export",
                snapshot_id="snapshot-1",
                data_coleta="2026-09-14T12:00:00+00:00",
                data_publicacao="2026-09-14T11:00:00+00:00",
                source_url="https://balanca.mdic.gov.br/example.csv",
                source_hash="snapshot-1",
                raw_artifact_ref="drive://raw/example.csv",
            )
            lines = [line for line in destination.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(stats["rows"], 2)
            self.assertEqual(stats["unique_record_ids"], 1)
            self.assertEqual(stats["exact_duplicate_rows"], 1)
            self.assertEqual(stats["dedupe_strategy"], "sqlite_disk_backed_exact")
            self.assertTrue(stats["audit_rows_preserved"])
            self.assertEqual(len(lines), 2)
            self.assertEqual(_count_ndjson_records(destination), 2)
            self.assertEqual(_count_unique_ndjson_record_ids(destination), 1)
            self.assertEqual(json.loads(lines[0])["co_ncm"], "12019000")
            self.assertEqual(json.loads(lines[1])["record_id"], json.loads(lines[0])["record_id"])
            self.assertEqual(list(Path(tmp).glob(".comex_dedupe_*.sqlite3")), [])

    def test_official_url_templates(self) -> None:
        self.assertEqual(
            dataset_url("ncm_export", 2026),
            "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/EXP_2026.csv",
        )
        self.assertEqual(
            dataset_url("municipio_sh4_export", 2026),
            "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/mun/EXP_2026_MUN.csv",
        )


if __name__ == "__main__":
    unittest.main()
