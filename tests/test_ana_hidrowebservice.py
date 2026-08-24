from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from collector.ana_hidrowebservice import (
    AUTH_PATH,
    INVENTORY_PATH,
    TELEMETRY_PATH,
    AnaHidroWebServiceClient,
    parse_stations,
    parse_telemetry,
)


class AnaParserTests(unittest.TestCase):
    def test_station_inventory_preserves_identity_and_location(self) -> None:
        payload = [{
            "CodigoEstacao": "12345678",
            "NomeEstacao": "Exemplo",
            "UF_Estacao": "MT",
            "Latitude": "-13,123",
            "Longitude": "-56,456",
            "NomeRio": "Rio Teste",
            "CodigoBacia": "1",
            "Operando": "Sim",
        }]
        rows = parse_stations(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].station_code, "12345678")
        self.assertEqual(rows[0].uf, "MT")
        self.assertAlmostEqual(rows[0].latitude or 0, -13.123)

    def test_telemetry_keeps_quality_status_and_units(self) -> None:
        payload = {"items": [{
            "codigoestacao": "12345678",
            "Data_Hora_Medicao": "2026-08-24T10:00:00",
            "Data_Atualizacao": "2026-08-24T10:10:00",
            "Chuva_Adotada": "12,5",
            "Status_Chuva_Adotada": 0,
            "Cota_Adotada": 350,
            "Status_Cota_Adotada": 1,
            "Vazao_Adotada": "420.7",
            "Status_Vazao_Adotada": 0,
        }]}
        rows = parse_telemetry(payload)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.evidence_class, "observado")
        self.assertEqual(row.evidence_subtype, "ana_telemetered_station")
        self.assertEqual(row.rainfall_status, 0)
        self.assertEqual(row.river_level_status, 1)
        self.assertAlmostEqual(row.rainfall_mm or 0, 12.5)
        self.assertAlmostEqual(row.discharge_m3_s or 0, 420.7)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class AnaClientTests(unittest.TestCase):
    @patch("collector.ana_hidrowebservice.urlopen")
    def test_token_is_cached_and_bearer_is_used(self, urlopen) -> None:
        urlopen.side_effect = [
            FakeResponse({"tokenautenticacao": "abc"}),
            FakeResponse([{"CodigoEstacao": "1", "UF_Estacao": "MT"}]),
            FakeResponse([{"CodigoEstacao": "2", "UF_Estacao": "MT"}]),
        ]
        client = AnaHidroWebServiceClient(identifier="id", password="pw")
        first = client.stations(uf="MT")
        second = client.stations(uf="MT")
        self.assertEqual(first[0].station_code, "1")
        self.assertEqual(second[0].station_code, "2")
        self.assertEqual(urlopen.call_count, 3)
        auth_request = urlopen.call_args_list[0].args[0]
        self.assertTrue(auth_request.full_url.endswith(AUTH_PATH))
        self.assertEqual(auth_request.get_header("Identificador"), "id")
        inventory_request = urlopen.call_args_list[1].args[0]
        self.assertIn(INVENTORY_PATH, inventory_request.full_url)
        self.assertEqual(inventory_request.get_header("Authorization"), "Bearer abc")

    @patch("collector.ana_hidrowebservice.urlopen")
    def test_telemetry_uses_documented_filter_contract(self, urlopen) -> None:
        urlopen.side_effect = [
            FakeResponse({"TokenAutenticacao": "xyz"}),
            FakeResponse([]),
        ]
        client = AnaHidroWebServiceClient(identifier="id", password="pw")
        client.telemetry("123", search_range="DIAS_30")
        request = urlopen.call_args_list[1].args[0]
        self.assertIn(TELEMETRY_PATH, request.full_url)
        self.assertIn("CodigoDaEstacao=123", request.full_url)
        self.assertIn("TipoFiltroData=DATA_LEITURA", request.full_url)
        self.assertIn("RangeIntervaloDeBusca=DIAS_30", request.full_url)

    def test_credentials_are_required_but_never_embedded(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                AnaHidroWebServiceClient()


if __name__ == "__main__":
    unittest.main()
