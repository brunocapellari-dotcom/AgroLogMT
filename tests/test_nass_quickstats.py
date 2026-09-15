from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from collector.models import SourceSpec
from collector.nass_quickstats import NassQuickStatsAdapter, _validated_params


class FakeResponse:
    def __init__(self, payload: dict, url: str) -> None:
        self._payload = json.dumps(payload).encode("utf-8")
        self._url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload

    def geturl(self) -> str:
        return self._url


class NassQuickStatsTests(unittest.TestCase):
    def spec(self, *, max_records: int = 50_000) -> SourceSpec:
        return SourceSpec(
            source_id="usda_nass_corn_weekly_fixture",
            name="NASS Corn Weekly fixture",
            group="dados",
            method="nass_quickstats",
            expected_frequency="weekly",
            file_extension="json",
            evidence_class="observado",
            options={
                "api_key_env": "NASS_API_KEY",
                "required_env_vars": ["NASS_API_KEY"],
                "timeout_seconds": 30,
                "max_records": max_records,
                "query": {
                    "source_desc": "SURVEY",
                    "sector_desc": "CROPS",
                    "commodity_desc": "CORN",
                    "agg_level_desc": "STATE",
                    "freq_desc": "WEEKLY",
                    "year": "2026",
                },
            },
        )

    @patch.dict(os.environ, {"NASS_API_KEY": "nass-secret"}, clear=False)
    @patch("collector.nass_quickstats.urlopen")
    def test_count_gate_precedes_data_and_masks_key(self, urlopen) -> None:
        row = {"commodity_desc": "CORN", "year": "2026", "Value": "90"}

        def fake(request, timeout):
            url = request.full_url
            self.assertIn("key=nass-secret", url)
            if "/get_counts/" in url:
                return FakeResponse({"count": "1"}, url)
            return FakeResponse({"data": [row]}, url)

        urlopen.side_effect = fake
        result = NassQuickStatsAdapter().fetch(self.spec())
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(json.loads(result.payload)["data"], [row])
        self.assertNotIn("nass-secret", result.observed_url)
        self.assertIn("key=%5BREDACTED%5D", result.observed_url)
        self.assertEqual(result.raw_payload, result.payload)

    @patch.dict(os.environ, {"NASS_API_KEY": "nass-secret"}, clear=False)
    @patch("collector.nass_quickstats.urlopen")
    def test_oversized_query_fails_before_data_download(self, urlopen) -> None:
        def fake(request, timeout):
            return FakeResponse({"count": "50001"}, request.full_url)

        urlopen.side_effect = fake
        with self.assertRaisesRegex(RuntimeError, "excede limite"):
            NassQuickStatsAdapter().fetch(self.spec())
        self.assertEqual(urlopen.call_count, 1)

    @patch.dict(os.environ, {"NASS_API_KEY": "nass-secret"}, clear=False)
    @patch("collector.nass_quickstats.urlopen")
    def test_count_mismatch_fails_closed(self, urlopen) -> None:
        responses = iter([
            FakeResponse({"count": "2"}, "https://quickstats.nass.usda.gov/api/get_counts/?key=nass-secret"),
            FakeResponse({"data": [{"Value": "1"}]}, "https://quickstats.nass.usda.gov/api/api_GET/?key=nass-secret"),
        ])
        urlopen.side_effect = lambda request, timeout: next(responses)
        with self.assertRaisesRegex(RuntimeError, "count mismatch"):
            NassQuickStatsAdapter().fetch(self.spec())

    def test_query_parameter_validation_blocks_reserved_and_malformed_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "reservado"):
            _validated_params({"key": "do-not-version"})
        with self.assertRaisesRegex(ValueError, "invalido"):
            _validated_params({"commodity_desc&evil": "CORN"})

    def test_missing_api_key_fails_closed(self) -> None:
        previous = os.environ.pop("NASS_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "NASS_API_KEY"):
                NassQuickStatsAdapter().fetch(self.spec())
        finally:
            if previous is not None:
                os.environ["NASS_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
