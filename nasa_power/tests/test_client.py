from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest
import requests

from nasa_power.client import (
    NASA_POWER_BASE_URL,
    NasaPowerApiError,
    NasaPowerClient,
    NasaPowerConnectionError,
    build_client,
)


def _json_response(status_code: int, payload) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = str(payload)
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _valid_payload(**overrides):
    payload = {
        "geometry": {"type": "Point", "coordinates": [-55.7217, -12.5453, 370.0]},
        "properties": {
            "parameter": {
                "T2M": {"20260101": 27.04, "20260102": -999.0},
                "PRECTOTCORR": {"20260101": 2.24, "20260102": 1.47},
            }
        },
        "header": {"fill_value": -999.0, "sources": ["SYN1DEG", "MERRA2", "POWER"]},
        "parameters": {
            "T2M": {"units": "C", "longname": "Temperature at 2 Meters"},
            "PRECTOTCORR": {"units": "mm/day", "longname": "Precipitation Corrected"},
        },
        "messages": [],
    }
    payload.update(overrides)
    return payload


class TestBuildClient:
    def test_locked_to_official_host(self):
        client = build_client(session=Mock())
        assert NASA_POWER_BASE_URL == "https://power.larc.nasa.gov"
        assert client.base_url == "https://power.larc.nasa.gov"
        assert isinstance(client, NasaPowerClient)

    def test_does_not_accept_a_base_url_override(self):
        import inspect

        params = inspect.signature(build_client).parameters
        assert "base_url" not in params

    def test_requests_still_target_original_host_after_module_constant_is_reassigned(self, monkeypatch):
        # nasa_power.client módulo importado sob outro nome para poder
        # reatribuir a constante sem afetar outros testes do processo.
        import nasa_power.client as client_module

        client = build_client(session=Mock())
        client._session.get.return_value = _json_response(200, _valid_payload())

        monkeypatch.setattr(client_module, "NASA_POWER_BASE_URL", "https://evil.example.com")
        client.daily_point(
            latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
        )

        called_url = client._session.get.call_args.args[0]
        assert called_url.startswith("https://power.larc.nasa.gov")


class TestDailyPointValidation:
    def test_rejects_latitude_out_of_range(self):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=999, longitude=-55.72, start="20260101", end="20260102", parameters=["T2M"]
            )

    def test_rejects_longitude_out_of_range(self):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5, longitude=999, start="20260101", end="20260102", parameters=["T2M"]
            )

    @pytest.mark.parametrize("bad_latitude", [None, "-12.5", float("nan"), float("inf"), True])
    def test_rejects_non_numeric_or_non_finite_latitude(self, bad_latitude):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=bad_latitude,
                longitude=-55.7,
                start="20260101",
                end="20260102",
                parameters=["T2M"],
            )

    @pytest.mark.parametrize("bad_longitude", [None, "-55.7", float("nan"), float("-inf")])
    def test_rejects_non_numeric_or_non_finite_longitude(self, bad_longitude):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5,
                longitude=bad_longitude,
                start="20260101",
                end="20260102",
                parameters=["T2M"],
            )

    @pytest.mark.parametrize("bad_community", [None, 123])
    def test_rejects_non_string_community(self, bad_community):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5,
                longitude=-55.7,
                start="20260101",
                end="20260102",
                parameters=["T2M"],
                community=bad_community,
            )

    def test_rejects_empty_parameters(self):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=[]
            )

    def test_rejects_a_bare_string_as_parameters(self):
        # "T2M" é uma Sequence[str] em Python (iterar dá "T","2","M") —
        # precisa ser recusado explicitamente, não virar 3 parâmetros.
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters="T2M"
            )

    @pytest.mark.parametrize("bad_parameters", [[""], ["   "], ["T2M", 123], [None]])
    def test_rejects_blank_or_non_string_parameter_items(self, bad_parameters):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5,
                longitude=-55.7,
                start="20260101",
                end="20260102",
                parameters=bad_parameters,
            )

    def test_rejects_invalid_community(self):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5,
                longitude=-55.7,
                start="20260101",
                end="20260102",
                parameters=["T2M"],
                community="bogus",
            )

    @pytest.mark.parametrize(
        "bad_date",
        ["2026-01-01", "202601", "", "2026010a", "20260231", "20261301", "00000000"],
    )
    def test_rejects_malformed_dates(self, bad_date):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start=bad_date, end="20260102", parameters=["T2M"]
            )

    def test_rejects_end_before_start(self):
        client = NasaPowerClient(session=Mock())
        with pytest.raises(ValueError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260110", end="20260101", parameters=["T2M"]
            )


class TestDailyPointParsing:
    def test_fill_value_becomes_none(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(200, _valid_payload())

        result = client.daily_point(
            latitude=-12.5453,
            longitude=-55.7217,
            start="20260101",
            end="20260102",
            parameters=["T2M", "PRECTOTCORR"],
        )

        assert result.values["T2M"]["20260101"] == 27.04
        assert result.values["T2M"]["20260102"] is None  # era -999.0 (fill_value)
        assert result.values["PRECTOTCORR"]["20260102"] == 1.47

    def test_parses_units_and_sources(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(200, _valid_payload())

        result = client.daily_point(
            latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
        )

        assert result.units["T2M"] == "C"
        assert "MERRA2" in result.sources

    def test_request_uses_read_only_daily_point_endpoint(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(200, _valid_payload())

        client.daily_point(
            latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
        )

        called_url = client._session.get.call_args.args[0]
        assert called_url == f"{NASA_POWER_BASE_URL}/api/temporal/daily/point"
        assert client._session.get.call_args.kwargs["allow_redirects"] is False

    def test_raises_on_non_dict_payload(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(200, ["not", "a", "dict"])
        with pytest.raises(NasaPowerApiError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )


class TestDailyPointMalformedPayload:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"geometry": {"coordinates": []}},
            {"header": None},
            {"properties": {"parameter": {"T2M": "not-a-dict"}}},
            {"parameters": {"T2M": None}},
            {"header": {"fill_value": -999.0, "sources": 123}},
            {"header": {"fill_value": 10**400, "sources": []}},  # excede o range de float (OverflowError)
        ],
    )
    def test_unexpected_schema_becomes_api_error_not_a_native_exception(self, overrides):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(200, _valid_payload(**overrides))

        with pytest.raises(NasaPowerApiError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )


class TestNasaPowerBaseUrlIntegrity:
    @pytest.mark.parametrize(
        "bad_base_url",
        ["http://power.larc.nasa.gov", "https://power.larc.nasa.gov:444", "https://evil.example.com"],
    )
    def test_rejects_base_url_variants_that_are_not_the_exact_official_origin(self, monkeypatch, bad_base_url):
        import nasa_power.client as client_module

        monkeypatch.setattr(client_module, "NASA_POWER_BASE_URL", bad_base_url)
        with pytest.raises(ValueError):
            client_module.NasaPowerClient(session=Mock())


class TestDailyPointErrors:
    def test_validation_error_uses_detail_format(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(
            422,
            {
                "detail": [
                    {"type": "less_than_equal", "loc": ["query", "latitude"], "msg": "Input should be <= 90"}
                ]
            },
        )
        with pytest.raises(NasaPowerApiError, match="latitude"):
            client.daily_point(
                latitude=45, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )

    @pytest.mark.parametrize("bad_loc", [None, 123, "not-a-list"])
    def test_validation_error_with_malformed_loc_still_raises_api_error(self, bad_loc):
        # loc=None reproduz um TypeError nativo em ".".join(...) se não
        # tratado — precisa continuar sendo NasaPowerApiError com o status
        # HTTP real, não uma exceção de tipo vazando de dentro do parsing
        # do corpo de erro.
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(
            422, {"detail": [{"msg": "bad input", "loc": bad_loc}]}
        )
        with pytest.raises(NasaPowerApiError, match="422"):
            client.daily_point(
                latitude=45, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )

    def test_validation_error_uses_messages_format(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.return_value = _json_response(
            422, {"header": "failed", "messages": ["One of your parameters is incorrect: BOGUS."]}
        )
        with pytest.raises(NasaPowerApiError, match="BOGUS"):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["BOGUS"]
            )

    def test_http_error_with_non_json_body_still_surfaces_the_status_code(self):
        # Um 500/502 de proxy costuma vir com HTML/texto, não JSON. O
        # status HTTP real precisa aparecer na mensagem em vez de virar
        # genericamente "não retornou JSON válido".
        client = NasaPowerClient(session=Mock())
        response = MagicMock()
        response.status_code = 500
        response.json.side_effect = ValueError("not json")
        response.text = "<html>Internal Server Error</html>"
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        client._session.get.return_value = response

        with pytest.raises(NasaPowerApiError, match="500"):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )

    def test_connection_error_becomes_nasa_power_connection_error(self):
        client = NasaPowerClient(session=Mock())
        client._session.get.side_effect = requests.ConnectionError("boom")
        with pytest.raises(NasaPowerConnectionError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )

    def test_redirect_is_not_followed(self):
        client = NasaPowerClient(session=Mock())
        response = _json_response(302, {})
        response.status_code = 302
        client._session.get.return_value = response
        with pytest.raises(NasaPowerApiError):
            client.daily_point(
                latitude=-12.5, longitude=-55.7, start="20260101", end="20260102", parameters=["T2M"]
            )
