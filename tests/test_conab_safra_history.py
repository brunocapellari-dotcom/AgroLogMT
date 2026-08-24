from __future__ import annotations

import unittest
from unittest.mock import patch

from collector.conab_safra_history import discover_publications


class ConabSafraHistoryTests(unittest.TestCase):
    @patch("collector.conab_safra_history._get_text")
    def test_discovers_and_orders_publications(self, get_text) -> None:
        listing = '''
        <a href="/conab/11o-levantamento-safra-2025-26">11</a>
        <a href="/conab/10o-levantamento-safra-2025-26">10</a>
        <a href="/conab/12o-levantamento-safra-2024-25">12</a>
        '''
        item = '<a href="previsao_de_safra.xlsx/view">xlsx</a>'
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


if __name__ == "__main__":
    unittest.main()
