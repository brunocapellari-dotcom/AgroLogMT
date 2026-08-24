from __future__ import annotations

import unittest
from unittest.mock import patch

from collector.conab_safra_history import discover_publications, extract_publication_time


class ConabSafraHistoryTests(unittest.TestCase):
    def test_extract_publication_time_from_official_metadata(self) -> None:
        html = '<meta property="article:published_time" content="2026-08-13T09:30:00-04:00">'
        self.assertEqual(extract_publication_time(html), "2026-08-13T13:30:00+00:00")

    def test_extract_publication_time_from_govbr_visible_text(self) -> None:
        html = '''
        <div class="documentPublished">
          <span>Publicado em</span>
          <span>13/08/2026 09h00</span>
          <span>Atualizado em 13/08/2026 09h48</span>
        </div>
        '''
        self.assertEqual(extract_publication_time(html), "2026-08-13T12:00:00+00:00")

    def test_missing_publication_time_returns_none(self) -> None:
        self.assertIsNone(extract_publication_time("<html><body>sem data</body></html>"))

    @patch("collector.conab_safra_history._get_text")
    def test_discovers_and_orders_publications(self, get_text) -> None:
        listing = '''
        <a href="/conab/11o-levantamento-safra-2025-26">11</a>
        <a href="/conab/10o-levantamento-safra-2025-26">10</a>
        <a href="/conab/12o-levantamento-safra-2024-25">12</a>
        '''
        item = '''
        <meta property="article:published_time" content="2026-08-13T09:30:00-04:00">
        <a href="previsao_de_safra.xlsx/view">xlsx</a>
        '''
        get_text.side_effect = [
            (listing, "https://www.gov.br/conab/list"),
            (item, "https://www.gov.br/conab/11o-levantamento-safra-2025-26"),
            (item, "https://www.gov.br/conab/10o-levantamento-safra-2025-26"),
            (item, "https://www.gov.br/conab/12o-levantamento-safra-2024-25"),
        ]
        rows = discover_publications("https://www.gov.br/conab/list")
        self.assertEqual([(r.safra, r.levantamento) for r in rows], [
            ("2025/26", 11), ("2025/26", 10), ("2024/25", 12)
        ])
        self.assertTrue(rows[0].attachment_url.endswith("/@@download/file"))
        self.assertEqual(rows[0].data_publicacao, "2026-08-13T13:30:00+00:00")
        self.assertEqual(rows[0].availability_basis, "official_page_timestamp")

    @patch("collector.conab_safra_history._get_text")
    def test_resolves_migrated_parent_from_nested_canonical_page(self, get_text) -> None:
        listing = '<a href="/conab/3o-levantamento-safra-2022-23">3</a>'
        parent = '''
        <div>Publicado em 17/09/2025 09h00</div>
        <a href="previsao_de_safra.xlsx/view">xlsx</a>
        '''
        nested = '<div><span>Publicado em</span><span>10/12/2022 09h00</span></div>'
        get_text.side_effect = [
            (listing, "https://www.gov.br/conab/list"),
            (parent, "https://www.gov.br/conab/3o-levantamento-safra-2022-23"),
            (nested, "https://www.gov.br/conab/3o-levantamento-safra-2022-23/3o-levantamento-safra-2022-23"),
        ]
        rows = discover_publications("https://www.gov.br/conab/list")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].data_publicacao, "2022-12-10T12:00:00+00:00")
        self.assertEqual(rows[0].availability_basis, "official_nested_page_timestamp")
        self.assertTrue(rows[0].item_url.endswith("/3o-levantamento-safra-2022-23/3o-levantamento-safra-2022-23"))


if __name__ == "__main__":
    unittest.main()
