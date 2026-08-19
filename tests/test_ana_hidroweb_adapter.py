from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from collector import adapters
from collector.adapters import AnaHidroWebAdapter
from collector.models import SourceSpec


class FakeResponse:
    def __init__(self, payload: dict, url: str) -> None:
        self._payload = json.dumps(payload).encode("utf-8")
        self._url = url
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload

    def geturl(self) -> str:
        return self._url


class AnaHidroWebAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        adapters._ANA_TOKEN_CACHE.clear()
        os.environ["ANA_IDENTIFICADOR"] = "identificador-teste"
        os.environ["ANA_SENHA"] = "senha-teste"

    def tearDown(self) -> None:
        adapters._ANA_TOKEN_CACHE.clear()
        os.environ.pop("ANA_IDENTIFICADOR", None)
        os.environ.pop("ANA_SENHA", None)

    @staticmethod
    def _spec(code: str) -> SourceSpec:
        return SourceSpec(
            source_id=f"ana_{code}",
            name=f"ANA {code}",
            group="dados",
            method="ana_hidroweb",
            file_extension="json",
            options={
                "station_code": code,
                "filter_type": "DATA_LEITURA",
                "search_range": "DIAS_30",
            },
        )

    def test_auth_headers_bearer_and_safe_observed_url(self) -> None:
        requests = []

        def fake_urlopen(request, timeout=0):
            requests.append(request)
            if request.full_url.endswith("/OAUth/v1"):
                return FakeResponse({"items": {"tokenautenticacao": "token-teste"}}, request.full_url)
            return FakeResponse(
                {"items": [{"codigoestacao": "15400000", "Cota_Adotada": 123}]},
                request.full_url,
            )

        with patch("collector.adapters.urlopen", side_effect=fake_urlopen):
            result = AnaHidroWebAdapter().fetch(self._spec("15400000"))

        self.assertEqual(len(requests), 2)
        auth_headers = dict(requests[0].header_items())
        data_headers = dict(requests[1].header_items())
        self.assertEqual(auth_headers.get("Identificador"), "identificador-teste")
        self.assertEqual(auth_headers.get("Senha"), "senha-teste")
        self.assertEqual(data_headers.get("Authorization"), "Bearer token-teste")
        self.assertIn("CodigoDaEstacao=15400000", result.observed_url)
        self.assertIn("RangeIntervaloDeBusca=DIAS_30", result.observed_url)
        self.assertNotIn("identificador-teste", result.observed_url)
        self.assertNotIn("senha-teste", result.observed_url)
        self.assertNotIn("token-teste", result.observed_url)

    def test_token_is_reused_between_stations(self) -> None:
        auth_calls = 0
        data_calls = 0

        def fake_urlopen(request, timeout=0):
            nonlocal auth_calls, data_calls
            if request.full_url.endswith("/OAUth/v1"):
                auth_calls += 1
                return FakeResponse({"items": {"tokenautenticacao": "token-cache"}}, request.full_url)
            data_calls += 1
            return FakeResponse({"items": []}, request.full_url)

        adapter = AnaHidroWebAdapter()
        with patch("collector.adapters.urlopen", side_effect=fake_urlopen):
            adapter.fetch(self._spec("15400000"))
            adapter.fetch(self._spec("15630000"))

        self.assertEqual(auth_calls, 1)
        self.assertEqual(data_calls, 2)

    def test_missing_credentials_fail_without_secret_value(self) -> None:
        os.environ.pop("ANA_SENHA", None)
        with self.assertRaisesRegex(RuntimeError, "ANA_SENHA") as ctx:
            AnaHidroWebAdapter().fetch(self._spec("15400000"))
        self.assertNotIn("senha-teste", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
