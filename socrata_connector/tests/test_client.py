from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest
import requests

from socrata_connector.client import (
    SocrataApiError,
    SocrataClient,
    SocrataConnectionError,
)

_BASE_URL = "https://example.socrata.test"


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
            SocrataClient(base_url="http://example.socrata.test")

    def test_defaults_allowed_hosts_to_base_url_host(self):
        # Sem allowed_hosts explícito, o único host aceito é o do próprio
        # base_url — não há caso de rejeição aqui por construção; a
        # rejeição de host fora da allowlist só é observável quando
        # allowed_hosts é passado explicitamente (ver teste abaixo).
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        assert client.base_url == _BASE_URL

    def test_accepts_host_in_explicit_allowlist(self):
        client = SocrataClient(
            base_url="https://mirror.example.com",
            allowed_hosts=frozenset({"example.socrata.test", "mirror.example.com"}),
            session=Mock(),
        )
        assert client.base_url == "https://mirror.example.com"

    def test_rejects_host_outside_explicit_allowlist(self):
        with pytest.raises(ValueError):
            SocrataClient(
                base_url="https://evil.example.com",
                allowed_hosts=frozenset({"example.socrata.test"}),
            )


class TestDatasetMetadata:
    def test_parses_columns_and_rows_updated_at(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.return_value = _json_response(
            200,
            {
                "name": "Some Dataset",
                "description": "desc",
                "attribution": "Agency",
                "license": None,
                "category": "Category",
                "rowsUpdatedAt": 1700000000,
                "columns": [
                    {"fieldName": "date", "dataTypeName": "calendar_date", "name": "date"},
                    {"fieldName": "value", "dataTypeName": "number", "name": "value"},
                ],
            },
        )

        metadata = client.dataset_metadata("abcd-1234")

        assert metadata.name == "Some Dataset"
        assert metadata.rows_updated_at is not None
        assert [c.field_name for c in metadata.columns] == ["date", "value"]

    def test_raises_on_non_dict_payload(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.return_value = _json_response(200, ["not", "a", "dict"])
        with pytest.raises(SocrataApiError):
            client.dataset_metadata("abcd-1234")

    def test_raises_on_http_error(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.return_value = _json_response(404, {"message": "not found"})
        with pytest.raises(SocrataApiError):
            client.dataset_metadata("does-not-exist")

    def test_connection_error_becomes_socrata_connection_error(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.side_effect = requests.ConnectionError("boom")
        with pytest.raises(SocrataConnectionError):
            client.dataset_metadata("abcd-1234")

    def test_redirect_is_not_followed(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        response = _json_response(302, {})
        response.headers = {"Location": "https://evil.example.com/steal"}
        client._session.get.return_value = response
        with pytest.raises(SocrataApiError):
            client.dataset_metadata("abcd-1234")
        _, kwargs = client._session.get.call_args
        assert kwargs["allow_redirects"] is False

    def test_missing_column_type_and_name_do_not_become_literal_none_string(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
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

        metadata = client.dataset_metadata("abcd-1234")

        assert metadata.columns[0].data_type == ""
        assert metadata.columns[0].display_name == ""


class TestQuery:
    def test_returns_records_and_forwards_soql_params(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.return_value = _json_response(200, [{"date": "2026-01-01"}])

        records = client.query(
            "abcd-1234", select="date,value", where="year=2026", order="date DESC", limit=10, offset=5
        )

        assert records == [{"date": "2026-01-01"}]
        _, kwargs = client._session.get.call_args
        assert kwargs["params"] == {
            "$limit": 10,
            "$offset": 5,
            "$select": "date,value",
            "$where": "year=2026",
            "$order": "date DESC",
        }

    def test_raises_on_non_list_payload(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.return_value = _json_response(200, {"error": "boom"})
        with pytest.raises(SocrataApiError):
            client.query("abcd-1234")

    def test_raises_on_list_with_non_dict_elements(self):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        client._session.get.return_value = _json_response(200, [1, "erro", None])
        with pytest.raises(SocrataApiError):
            client.query("abcd-1234")

    @pytest.mark.parametrize("limit", [0, -1, 50001, 1.5, True])
    def test_rejects_invalid_limit(self, limit):
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        with pytest.raises(ValueError):
            client.query("abcd-1234", limit=limit)

    @pytest.mark.parametrize("offset", [-1, 2.7, False])
    def test_rejects_invalid_offset(self, offset):
        # offset=False é recusado mesmo sendo tecnicamente int(0) e >= 0 —
        # apenas inteiros "de verdade" são aceitos.
        client = SocrataClient(base_url=_BASE_URL, session=Mock())
        with pytest.raises(ValueError):
            client.query("abcd-1234", offset=offset)
