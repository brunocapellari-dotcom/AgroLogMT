from __future__ import annotations

import io
import unittest

from collector.comexstat import chunked, dataset_url, iter_rows, parse_text


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

    def test_chunked_never_requires_full_materialization(self) -> None:
        rows = ({"i": i} for i in range(5))
        batches = list(chunked(rows, size=2))
        self.assertEqual([len(b) for b in batches], [2, 2, 1])

    def test_official_url_templates(self) -> None:
        self.assertEqual(dataset_url("ncm_export", 2026), "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/ncm/EXP_2026.csv")
        self.assertEqual(dataset_url("municipio_sh4_export", 2026), "https://balanca.mdic.gov.br/balanca/bd/comexstat-bd/mun/EXP_2026_MUN.csv")


if __name__ == "__main__":
    unittest.main()
