from __future__ import annotations

import unittest

from collector.adapters import extract_html_links, select_first_matching_link


class GovBrAdapterTests(unittest.TestCase):
    def test_extract_and_select_latest_item(self) -> None:
        html = '''
        <a href="/conab/safra/11o-levantamento-safra-2025-26/">11º</a>
        <a href="/conab/safra/10o-levantamento-safra-2025-26/">10º</a>
        '''
        base = "https://www.gov.br/conab/safra/"
        links = extract_html_links(html, base)
        selected = select_first_matching_link(
            links, r"/\d+o-levantamento-safra-", same_host_as=base
        )
        self.assertEqual(selected, "https://www.gov.br/conab/safra/11o-levantamento-safra-2025-26/")

    def test_external_host_is_rejected(self) -> None:
        links = [
            "https://evil.example/11o-levantamento-safra-2025-26/",
            "https://www.gov.br/conab/11o-levantamento-safra-2025-26/",
        ]
        selected = select_first_matching_link(
            links, r"/\d+o-levantamento-safra-", same_host_as="https://www.gov.br/conab/"
        )
        self.assertTrue(selected.startswith("https://www.gov.br/"))

    def test_attachment_regex(self) -> None:
        html = '''
        <a href="boletim.pdf/view">PDF</a>
        <a href="site_previsao_de_safra-por-produto-ago-2026.xlsx/view">XLSX</a>
        '''
        links = extract_html_links(html, "https://www.gov.br/conab/levantamento/")
        selected = select_first_matching_link(
            links, r"\.xlsx(?:/view)?(?:$|[?#])", same_host_as="https://www.gov.br/conab/levantamento/"
        )
        self.assertTrue(selected.endswith(".xlsx/view"))


if __name__ == "__main__":
    unittest.main()
