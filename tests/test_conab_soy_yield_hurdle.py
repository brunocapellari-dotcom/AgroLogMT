from __future__ import annotations

import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from collector.conab_safra_history import SafraPublication
from scripts.build_conab_soy_yield_hurdle import _download_verified_publication, _season_start


class ConabSoyYieldHurdleTests(unittest.TestCase):
    def test_season_start_accepts_short_and_long_labels(self) -> None:
        self.assertEqual(_season_start("20/21"), 2020)
        self.assertEqual(_season_start("25/26"), 2025)
        self.assertEqual(_season_start("2022/23"), 2022)

    def test_season_start_rejects_invalid_label(self) -> None:
        with self.assertRaises(ValueError):
            _season_start("2025")

    @patch("scripts.build_conab_soy_yield_hurdle._publication_from_item")
    @patch("scripts.build_conab_soy_yield_hurdle._download")
    def test_moved_attachment_is_reresolved_from_same_official_item(self, download, resolve) -> None:
        stale = "https://www.gov.br/conab/stale.xlsx/@@download/file"
        fresh = "https://www.gov.br/conab/fresh.xlsx/@@download/file"
        download.side_effect = [
            HTTPError(stale, 404, "Not Found", hdrs=None, fp=io.BytesIO()),
            b"xlsx-bytes",
        ]
        resolve.return_value = SafraPublication(
            item_url="https://www.gov.br/conab/item",
            attachment_url=fresh,
            safra="2024/25",
            levantamento=12,
            data_publicacao="2025-09-11T12:00:00+00:00",
            availability_basis="official_page_timestamp",
        )
        payload, resolved_url, mode = _download_verified_publication({
            "attachment_url": stale,
            "item_url": "https://www.gov.br/conab/item",
            "safra": "2024/25",
            "levantamento": 12,
        })
        self.assertEqual(payload, b"xlsx-bytes")
        self.assertEqual(resolved_url, fresh)
        self.assertEqual(mode, "official_item_reresolved")

    @patch("scripts.build_conab_soy_yield_hurdle._publication_from_item")
    @patch("scripts.build_conab_soy_yield_hurdle._download")
    def test_reresolution_rejects_identity_drift(self, download, resolve) -> None:
        stale = "https://www.gov.br/conab/stale.xlsx/@@download/file"
        download.side_effect = HTTPError(stale, 404, "Not Found", hdrs=None, fp=io.BytesIO())
        resolve.return_value = SafraPublication(
            item_url="https://www.gov.br/conab/item",
            attachment_url="https://www.gov.br/conab/fresh.xlsx/@@download/file",
            safra="2023/24",
            levantamento=12,
            data_publicacao="2024-09-01T12:00:00+00:00",
            availability_basis="official_page_timestamp",
        )
        with self.assertRaises(RuntimeError):
            _download_verified_publication({
                "attachment_url": stale,
                "item_url": "https://www.gov.br/conab/item",
                "safra": "2024/25",
                "levantamento": 12,
            })


if __name__ == "__main__":
    unittest.main()
