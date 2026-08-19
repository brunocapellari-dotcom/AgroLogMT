from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from collector.adapters import ApiDataGovAdapter
from collector.models import SourceSpec


class _Headers:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {"Content-Type": "application/json"}

    def get(self, key: str, default=None):
        return self.values.get(key, default)


class _Response:
    def __init__(self, payload: bytes, url: str) -> None:
        self._payload = payload
        self._url = url
        self.headers = _Headers()

    def read(self) -> bytes:
        return self._payload

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ApiDataGovAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("DATA_GOV_API_KEY", None)

    def tearDown(self) -> None:
        os.environ.pop("DATA_GOV_API_KEY", None)

    def test_requires_secret_from_environment(self) -> None:
        spec = SourceSpec(
            source_id="usda_test",
            name="USDA Test",
            group="dados",
            method="api_data_gov",
            url="https://api.fas.usda.gov/api/psd/commodities",
            file_extension="json",
        )
        with self.assertRaisesRegex(RuntimeError, "DATA_GOV_API_KEY"):
            ApiDataGovAdapter().fetch(spec)

    def test_sends_key_in_header_and_not_url(self) -> None:
        os.environ["DATA_GOV_API_KEY"] = "test-secret-key"
        spec = SourceSpec(
            source_id="usda_test",
            name="USDA Test",
            group="dados",
            method="api_data_gov",
            url="https://api.fas.usda.gov/api/psd/commodities",
            file_extension="json",
            options={"api_key_env": "DATA_GOV_API_KEY"},
        )
        captured = {}

        def fake_urlopen(request, timeout=60):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return _Response(b"[]", request.full_url)

        with patch("collector.adapters.urlopen", fake_urlopen):
            result = ApiDataGovAdapter().fetch(spec)

        header_values = {key.lower(): value for key, value in captured["headers"].items()}
        self.assertEqual(header_values.get("x-api-key"), "test-secret-key")
        self.assertNotIn("test-secret-key", captured["url"])
        self.assertEqual(result.observed_url, spec.url)
        self.assertEqual(result.payload, b"[]")


if __name__ == "__main__":
    unittest.main()
