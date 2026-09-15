from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from collector.adapters import AcquisitionResult, EnvQueryHttpAdapter
from collector.models import SourceSpec


class AdapterSecretSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = SourceSpec(
            source_id="nass_fixture",
            name="NASS fixture",
            group="dados",
            method="http_env_query",
            url="https://quickstats.nass.usda.gov/api/api_GET/?commodity_desc=CORN&format=JSON",
            file_extension="json",
            options={
                "query_param_name": "key",
                "query_env_var": "NASS_API_KEY",
                "timeout_seconds": 30,
            },
        )

    @patch.dict(os.environ, {"NASS_API_KEY": "secret-123"}, clear=False)
    @patch("collector.adapters._http_get")
    def test_query_secret_is_used_for_request_but_masked_from_observed_url(self, http_get) -> None:
        def fake(url: str, **kwargs):
            self.assertIn("secret-123", url)
            return AcquisitionResult(
                payload=b'{"data":[]}',
                observed_url=url,
                content_type="application/json",
            )

        http_get.side_effect = fake
        result = EnvQueryHttpAdapter().fetch(self.spec)
        self.assertNotIn("secret-123", result.observed_url)
        self.assertIn("key=%5BREDACTED%5D", result.observed_url)
        self.assertEqual(result.payload, b'{"data":[]}')

    @patch.dict(os.environ, {"NASS_API_KEY": "secret-123"}, clear=False)
    @patch("collector.adapters._http_get")
    def test_query_secret_is_redacted_from_transport_exception(self, http_get) -> None:
        http_get.side_effect = RuntimeError(
            "failed https://quickstats.nass.usda.gov/api/api_GET/?key=secret-123"
        )
        with self.assertRaises(RuntimeError) as caught:
            EnvQueryHttpAdapter().fetch(self.spec)
        self.assertNotIn("secret-123", str(caught.exception))
        self.assertIn("[REDACTED]", str(caught.exception))

    def test_missing_secret_fails_closed(self) -> None:
        previous = os.environ.pop("NASS_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "NASS_API_KEY"):
                EnvQueryHttpAdapter().fetch(self.spec)
        finally:
            if previous is not None:
                os.environ["NASS_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
