from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from collector.models import SourceSpec
from collector.p0_adapters import AnaHidroAdoptedAdapter, BcbPtaxDailyAdapter, P0AcquisitionError


class FakeResponse:
    def __init__(self, body=None, status=200, headers=None, content=None):
        self._body = body
        self.status_code = status
        self.headers = headers or {}
        if content is not None:
            self.content = content
        elif body is None:
            self.content = b""
        else:
            self.content = json.dumps(body).encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


class TestBcbPtaxDailyAdapter(unittest.TestCase):
    def test_selects_latest_official_observation_and_preserves_closing_csv(self):
        spec = SourceSpec(source_id="bcb_ptax_usd_daily", name="PTAX", group="dados", method="bcb_ptax_daily")
        discovery = {
            "value": [
                {"cotacaoCompra": 5.2, "cotacaoVenda": 5.21, "dataHoraCotacao": "2026-08-21 13:10:00.000"},
                {"cotacaoCompra": 5.15, "cotacaoVenda": 5.16, "dataHoraCotacao": "2026-08-24 13:08:00.000"},
            ]
        }
        raw = b"220;A;USD;5,1500;5,1600;1,0000;1,0000\r\n"
        calls = [
            FakeResponse(discovery, headers={"Content-Type": "application/json"}),
            FakeResponse(content=raw, headers={"Content-Type": "application/octet-stream"}),
        ]
        with patch("collector.p0_adapters.requests.get", side_effect=calls):
            result = BcbPtaxDailyAdapter().fetch(spec)
        body = json.loads(result.payload)
        self.assertEqual(body["latest"]["dataHoraCotacao"][:10], "2026-08-24")
        self.assertEqual(body["source"], "BCB_DEPIN_PTAX")
        self.assertEqual(body["raw_crosscheck"], "matched")
        self.assertEqual(result.raw_payload, raw)
        self.assertTrue(result.observed_url.endswith("/20260824.csv"))
        self.assertEqual(result.content_type, "application/octet-stream")

    def test_fails_closed_when_csv_diverges_from_olinda(self):
        spec = SourceSpec(source_id="bcb_ptax_usd_daily", name="PTAX", group="dados", method="bcb_ptax_daily")
        discovery = {
            "value": [
                {"cotacaoCompra": 5.15, "cotacaoVenda": 5.16, "dataHoraCotacao": "2026-08-24 13:08:00.000"},
            ]
        }
        raw = b"220;A;USD;5,1400;5,1600;1,0000;1,0000\n"
        calls = [FakeResponse(discovery), FakeResponse(content=raw)]
        with patch("collector.p0_adapters.requests.get", side_effect=calls):
            with self.assertRaises(P0AcquisitionError):
                BcbPtaxDailyAdapter().fetch(spec)

    def test_fails_closed_without_quote(self):
        spec = SourceSpec(source_id="bcb_ptax_usd_daily", name="PTAX", group="dados", method="bcb_ptax_daily")
        with patch("collector.p0_adapters.requests.get", return_value=FakeResponse({"value": []})):
            with self.assertRaises(P0AcquisitionError):
                BcbPtaxDailyAdapter().fetch(spec)


class TestAnaHidroAdoptedAdapter(unittest.TestCase):
    def setUp(self):
        self.old_user = os.environ.get("ANA_IDENTIFICADOR")
        self.old_password = os.environ.get("ANA_SENHA")
        os.environ["ANA_IDENTIFICADOR"] = "TEST_USER_SECRET"
        os.environ["ANA_SENHA"] = "TEST_PASSWORD_SECRET"

    def tearDown(self):
        if self.old_user is None:
            os.environ.pop("ANA_IDENTIFICADOR", None)
        else:
            os.environ["ANA_IDENTIFICADOR"] = self.old_user
        if self.old_password is None:
            os.environ.pop("ANA_SENHA", None)
        else:
            os.environ["ANA_SENHA"] = self.old_password

    def test_token_and_credentials_not_persisted(self):
        token = "TEST_TOKEN_SECRET"
        auth = FakeResponse({"items": {"tokenautenticacao": token}})
        data = FakeResponse(
            {
                "items": [
                    {
                        "codigoestacao": "15400000",
                        "Chuva_Adotada": "0.00",
                        "Chuva_Adotada_Status": "0",
                        "Cota_Adotada": "781.00",
                        "Cota_Adotada_Status": "0",
                        "Vazao_Adotada": "13225.42",
                        "Vazao_Adotada_Status": "0",
                        "Data_Atualizacao": "2026-08-25 10:00:00.000",
                        "Data_Hora_Medicao": "2026-08-25 09:45:00.0",
                    }
                ]
            }
        )
        calls = [auth, data]

        def fake_get(*args, **kwargs):
            return calls.pop(0)

        spec = SourceSpec(
            source_id="ana_hidroweb_m04_stations",
            name="ANA",
            group="dados",
            method="ana_hidroweb_adopted",
            options={"station_codes": ["15400000"], "range_filter": "DIAS_30"},
        )
        with patch("collector.p0_adapters.requests.get", side_effect=fake_get):
            result = AnaHidroAdoptedAdapter().fetch(spec)
        text = result.payload.decode("utf-8")
        self.assertNotIn("TEST_USER_SECRET", text)
        self.assertNotIn("TEST_PASSWORD_SECRET", text)
        self.assertNotIn(token, text)
        body = json.loads(text)
        self.assertFalse(body["token_exposed"])
        self.assertEqual(body["items"][0]["codigoestacao"], "15400000")

    def test_missing_secret_fails_closed(self):
        os.environ.pop("ANA_SENHA", None)
        spec = SourceSpec(
            source_id="ana_hidroweb_m04_stations",
            name="ANA",
            group="dados",
            method="ana_hidroweb_adopted",
            options={"station_codes": ["15400000"]},
        )
        with self.assertRaises(P0AcquisitionError):
            AnaHidroAdoptedAdapter().fetch(spec)


if __name__ == "__main__":
    unittest.main()
