from __future__ import annotations

import unittest
from datetime import date

from collector.official_lineup_pdf import (
    PdfTable,
    _validate_pdf_url,
    discover_paranagua_landing_pages,
    discover_pdf_link_from_landing,
    parse_itaqui_tables,
    parse_paranagua_tables,
)
from collector.lineup_normalizer import normalize_lineup_row


class MaritimeOfficialLineupPdfTests(unittest.TestCase):
    def test_itaqui_table_preserves_informed_status_and_quantities(self) -> None:
        table = PdfTable(
            page_number=1,
            rows=(
                (
                    "Berço / Berth", "Status", "IMO", "Navio / Vessel", "LOA", "Boca / Beam", "DWT",
                    "Calado de Chegada", "Calado de saída", "Prev. Chegada / ETA / NOR",
                    "Prev. Atrac. / ETB", "Prev. Desatrac. / ETS", "Operação", "Produto / Cargo",
                    "Qtde.", "Agente / Agency", "Operador Portuário", "Import./Export.", "Observações",
                ),
                (
                    "BERÇO 103 Loa: 229 Prof.: 15m DWT: 100.000 Atualização: 27/02 -10:00",
                    "FUNDEADO", "9967677", "MAGMA INTEGRITY", "199,90", "32,26", "63.697",
                    "7,35", "11,91", "13/2/26 3:36", "27/2", "2/3", "C", "SOJA",
                    "52.138", "FERTIMPORT", "TEGRAM", "BUNGE ALIMENTOS", "",
                ),
                (
                    "", "ESPERADO", "9561863", "INCE ILGAZ", "224,94", "32,26", "76.579",
                    "7,38", "13,30", "17/2/26 4:45", "2/3", "5/3", "C", "SOJA",
                    "66.071", "WILSON SONS", "TEGRAM", "ALZ", "",
                ),
            ),
        )
        rows = parse_itaqui_tables([table], reference_date=date(2026, 2, 27))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["terminal"], "BERCO_103")
        self.assertEqual(rows[1]["terminal"], "BERCO_103")
        self.assertEqual(rows[0]["quantidade_t"], "52138")
        self.assertEqual(rows[0]["status"], "FUNDEADO")

        call = normalize_lineup_row(
            rows[0],
            port_id="ITAQUI",
            snapshot_id="pdf-1",
            collected_at="2026-02-27T13:30:00Z",
            source_id="emap_itaqui_lineup",
            source_timezone="America/Sao_Paulo",
        )
        self.assertEqual(call.lineup_status, "ARRIVED_WAITING")
        self.assertEqual(call.planned_volume_t, 52138.0)
        self.assertEqual(call.eta_utc.isoformat(), "2026-02-13T06:36:00+00:00")
        self.assertEqual(call.imo, "9967677")

    def test_itaqui_skips_berth_free_and_maintenance_rows(self) -> None:
        table = PdfTable(
            page_number=1,
            rows=(
                ("Berço / Berth", "Status", "IMO", "Navio / Vessel", "Prev. Chegada / ETA / NOR", "Produto / Cargo", "Qtde."),
                ("BERÇO 103", "ATRACADO", "BL", "BERÇO LIVRE", "27/2/26 10:00", "BERÇO LIVRE", "100"),
                ("", "ATRACADO", "MN", "MANUTENÇÃO", "27/2/26 10:00", "MANUTENÇÃO", "100"),
            ),
        )
        self.assertEqual(parse_itaqui_tables([table], reference_date=date(2026, 2, 27)), [])

    def test_paranagua_programmed_table_and_commodity_volume(self) -> None:
        table = PdfTable(
            page_number=1,
            rows=(
                ("Line up do Corredor de Exportação", "", "", "", "", "", "", "", "", "", "", "", "", ""),
                ("SEQ", "DATA", "NAVIO", "AGÊNCIA", "Nº PROG", "CHEGADA", "", "PRODUTO", "SOJA", "FARELO", "MILHO", "AÇÚCAR", "LOA", "CONSIGNAÇÃO", "BERÇO"),
                ("1", "", "AMERICA", "FERTIMPORT", "79.373", "17/04", "1:12", "SOJA", "70.563", "", "", "", "200", "EXPORTADOR X", "201 ( PRE-PROG.)"),
                ("2", "", "BRILLIANT TRADER", "AMART", "79.437", "18/04", "5:48", "MILHO", "", "", "24.200", "", "210", "EXPORTADOR Y", "201"),
            ),
        )
        rows = parse_paranagua_tables([table], reference_date=date(2026, 4, 17), series="EXPORT_LESTE")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["call_id"], "EXPORT_LESTE:79.373")
        self.assertEqual(rows[0]["quantidade_t"], "70563")
        self.assertEqual(rows[0]["carga"], "SOJA")
        self.assertEqual(rows[0]["eta"], "17/04/2026 01:12")
        self.assertEqual(rows[1]["quantidade_t"], "24200")
        self.assertEqual(rows[1]["status"], "PROGRAMMED")

    def test_paranagua_refuses_atracados_section(self) -> None:
        table = PdfTable(
            page_number=1,
            rows=(
                ("Navios Atracados", "", "", "", "", "", ""),
                ("NAVIO", "Nº PROG", "CHEGADA", "PRODUTO", "SOJA", "MILHO", "BERÇO"),
                ("ALREADY BERTHED", "999", "17/04 1:12", "SOJA", "50.000", "", "201"),
            ),
        )
        self.assertEqual(
            parse_paranagua_tables([table], reference_date=date(2026, 4, 17), series="EXPORT_OESTE"),
            [],
        )

    def test_paranagua_index_discovers_latest_lineups_not_atas(self) -> None:
        index_url = "https://www.portosdoparana.pr.gov.br/Operacional/Pagina/Atas-do-Corredor-de-Exportacao"
        html = """
        <a href="/Arquivo/OLD">LINE-UP CORREDOR OESTE 09/09/2026</a>
        <a href="/Arquivo/NEW-W">LINE-UP CORREDOR OESTE 11/09/2026</a>
        <a href="/Arquivo/ATA-W">ATA DE ATRACAÇÃO CORREDOR OESTE 11/09/2026</a>
        <a href="/Arquivo/NEW-E">LINE-UP CORREDOR LESTE 11/09/2026</a>
        """
        result = discover_paranagua_landing_pages(html, index_url)
        self.assertTrue(result["EXPORT_OESTE"].endswith("/Arquivo/NEW-W"))
        self.assertTrue(result["EXPORT_LESTE"].endswith("/Arquivo/NEW-E"))
        self.assertNotIn("ATA", " ".join(result.values()))

    def test_paranagua_import_solids_series_is_discoverable(self) -> None:
        index_url = "https://www.portosdoparana.pr.gov.br/Operacional/Pagina/Graneis-de-Importacao-e-Carga-Geral"
        html = '<a href="/Arquivo/IMP">LINE UP DE GRANÉIS SÓLIDOS DE IMPORTAÇÃO - 12/09/2026 8h00min</a>'
        result = discover_paranagua_landing_pages(html, index_url)
        self.assertTrue(result["IMPORT_SOLIDOS"].endswith("/Arquivo/IMP"))

    def test_landing_pdf_is_unique_and_same_official_host(self) -> None:
        landing = "https://www.portosdoparana.pr.gov.br/Arquivo/LINE-CORREDOR-LESTE-11092026"
        html = '<a href="/sites/portos/arquivos_restritos/files/documento/2026-09/LINEUP11092026.pdf">LINEUP11092026.pdf</a>'
        pdf = discover_pdf_link_from_landing(html, landing)
        self.assertTrue(pdf.endswith("LINEUP11092026.pdf"))
        _validate_pdf_url(pdf)

    def test_pdf_url_allowlist_fails_closed(self) -> None:
        _validate_pdf_url("https://www.portosdoparana.pr.gov.br/x.pdf")
        _validate_pdf_url("https://www.portodoitaqui.com/x.pdf")
        with self.assertRaises(ValueError):
            _validate_pdf_url("http://www.portodoitaqui.com/x.pdf")
        with self.assertRaises(ValueError):
            _validate_pdf_url("https://example.com/x.pdf")


if __name__ == "__main__":
    unittest.main()
