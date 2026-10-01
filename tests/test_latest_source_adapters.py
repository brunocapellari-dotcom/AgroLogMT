from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from collector.adapters import AcquisitionResult, CkanResourceAdapter, HtmlLatestAttachmentAdapter
from collector.models import SourceSpec


class TestLatestSourceAdapters(unittest.TestCase):
    def test_ckan_regex_prefers_latest_resource(self) -> None:
        spec = SourceSpec(
            source_id="rntrc",
            name="RNTRC",
            group="dados",
            method="ckan",
            options={
                "base_url": "https://dados.example.gov.br",
                "dataset_id": "dataset",
                "resource_name_regex": r"RNTRC$",
                "prefer_latest": True,
                "max_response_bytes": 1024 * 1024,
            },
        )
        package = {
            "success": True,
            "result": {
                "resources": [
                    {
                        "name": "Jan26 - RNTRC",
                        "url": "https://dados.example.gov.br/jan.csv",
                        "last_modified": "2026-02-01T00:00:00",
                    },
                    {
                        "name": "Fev26 - RNTRC",
                        "url": "https://dados.example.gov.br/fev.csv",
                        "last_modified": "2026-03-01T00:00:00",
                    },
                ]
            },
        }
        responses = [
            AcquisitionResult(
                payload=json.dumps(package).encode(),
                observed_url="https://dados.example.gov.br/api/3/action/package_show?id=dataset",
                content_type="application/json",
            ),
            AcquisitionResult(
                payload=b"latest",
                observed_url="https://dados.example.gov.br/fev.csv",
                content_type="text/csv",
            ),
        ]
        with patch("collector.adapters._http_get", side_effect=responses) as mocked:
            result = CkanResourceAdapter().fetch(spec)
        self.assertEqual(result.payload, b"latest")
        self.assertEqual(mocked.call_args_list[1].args[0], "https://dados.example.gov.br/fev.csv")

    def test_html_latest_attachment_converts_govbr_view_to_download(self) -> None:
        spec = SourceSpec(
            source_id="anp_diesel",
            name="ANP diesel",
            group="dados",
            method="html_latest_attachment",
            url="https://www.gov.br/anp/listing",
            options={
                "attachment_url_regex": r"/2026/.*diesel.*\.csv/view$",
                "max_response_bytes": 1024 * 1024,
            },
        )
        listing = b'<a href="/anp/2026/08-diesel.csv/view">Agosto</a>'
        responses = [
            AcquisitionResult(
                payload=listing,
                observed_url="https://www.gov.br/anp/listing",
                content_type="text/html",
            ),
            AcquisitionResult(
                payload=b"csv",
                observed_url="https://www.gov.br/anp/2026/08-diesel.csv/@@download/file",
                content_type="text/csv",
            ),
        ]
        with patch("collector.adapters._http_get", side_effect=responses) as mocked:
            result = HtmlLatestAttachmentAdapter().fetch(spec)
        self.assertEqual(result.payload, b"csv")
        self.assertEqual(
            mocked.call_args_list[1].args[0],
            "https://www.gov.br/anp/2026/08-diesel.csv/@@download/file",
        )


if __name__ == "__main__":
    unittest.main()
