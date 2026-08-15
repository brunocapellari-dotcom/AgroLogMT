from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest
import requests

from usda_agtransport.client import (
    SocrataApiError,
    SocrataClient,
    SocrataConnectionError,
)


def _json_response(status_code: int, payload) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.text = str(payload)
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class TestInit:
    def test_rejects_non_https_base_url(self):
        with pytest.raises(ValueError):
            SocrataClient(base_url="http://agtransport.usda.gov")

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://127.0.0.1",
            "https://localhost",
            "https://evil.example.com",
        ],
    )
    def test_rejects_hosts_outside_allowlist(self, base_url):
        with pytest.raises(ValueError):
            SocrataClient(base_url=base_url)


class TestDatasetMetadata:
    def test_parses_columns_and_rows_updated_at(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(
            200,
            {
                "name": "Grain Transportation Cost Indicators",
                "description": "desc",
                "attribution": "USDA/AMS/TM/TSD",
                "license": None,
                "category": "Bulk",
                "rowsUpdatedAt": 1700000000,
                "columns": [
                    {"fieldName": "date", "dataTypeName": "calendar_date", "name": "date"},
                    {"fieldName": "truck", "dataTypeName": "number", "name": "truck"},
                ],
            },
        )

        metadata = client.dataset_metadata("8uye-ieij")

        assert metadata.name == "Grain Transportation Cost Indicators"
        assert metadata.rows_updated_at is not None
        assert [c.field_name for c in metadata.columns] == ["date", "truck"]

    def test_raises_on_non_dict_payload(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(200, ["not", "a", "dict"])
        with pytest.raises(SocrataApiError):
            client.dataset_metadata("8uye-ieij")

    def test_raises_on_http_error(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(404, {"message": "not found"})
        with pytest.raises(SocrataApiError):
            client.dataset_metadata("does-not-exist")

    def test_connection_error_becomes_socrata_connection_error(self):
        client = SocrataClient(session=Mock())
        client._session.get.side_effect = requests.ConnectionError("boom")
        with pytest.raises(SocrataConnectionError):
            client.dataset_metadata("8uye-ieij")

    def test_redirect_is_not_followed(self):
        client = SocrataClient(session=Mock())
        response = _json_response(302, {})
        response.headers = {"Location": "https://evil.example.com/steal"}
        client._session.get.return_value = response
        with pytest.raises(SocrataApiError):
            client.dataset_metadata("8uye-ieij")
        _, kwargs = client._session.get.call_args
        assert kwargs["allow_redirects"] is False

    def test_missing_column_type_and_name_do_not_become_literal_none_string(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(
            200,
            {
                "name": "x",
                "description": "",
                "attribution": "",
                "license": None,
                "category": None,
                "rowsUpdatedAt": None,
                "columns": [{"fieldName": "date"}],
            },
        )

        metadata = client.dataset_metadata("8uye-ieij")

        assert metadata.columns[0].data_type == ""
        assert metadata.columns[0].display_name == ""


class TestQuery:
    def test_returns_records_and_forwards_soql_params(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(200, [{"date": "2026-01-01"}])

        records = client.query(
            "8uye-ieij", select="date,truck", where="year=2026", order="date DESC", limit=10, offset=5
        )

        assert records == [{"date": "2026-01-01"}]
        _, kwargs = client._session.get.call_args
        assert kwargs["params"] == {
            "$limit": 10,
            "$offset": 5,
            "$select": "date,truck",
            "$where": "year=2026",
            "$order": "date DESC",
        }

    def test_raises_on_non_list_payload(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(200, {"error": "boom"})
        with pytest.raises(SocrataApiError):
            client.query("8uye-ieij")

    def test_raises_on_list_with_non_dict_elements(self):
        client = SocrataClient(session=Mock())
        client._session.get.return_value = _json_response(200, [1, "erro", None])
        with pytest.raises(SocrataApiError):
            client.query("8uye-ieij")

    @pytest.mark.parametrize("limit", [0, -1, 50001, 1.5, True])
    def test_rejects_invalid_limit(self, limit):
        client = SocrataClient(session=Mock())
        with pytest.raises(ValueError):
            client.query("8uye-ieij", limit=limit)

    @pytest.mark.parametrize("offset", [-1, 2.7, False])
    def test_rejects_invalid_offset(self, offset):
        # offset=False é recusado mesmo sendo tecnicamente int(0) e >= 0 —
        # apenas inteiros "de verdade" são aceitos.
        client = SocrataClient(session=Mock())
        with pytest.raises(ValueError):
            client.query("8uye-ieij", offset=offset)
