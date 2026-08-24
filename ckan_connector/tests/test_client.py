from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from ckan_connector.client import (
    CkanApiError,
    CkanClient,
    CkanConnectionError,
    ResourceMetadata,
    UnsafeUrlError,
)


def _json_response(status_code: int, payload) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _streaming_response(status_code: int, chunks: list[bytes], headers: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.iter_content.return_value = chunks
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class TestPackageList:
    def test_returns_ids_on_success(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(
            200, {"success": True, "result": ["a", "b"]}
        )
        assert client.package_list() == ["a", "b"]

    def test_raises_on_api_error(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(
            200, {"success": False, "error": {"message": "boom"}}
        )
        with pytest.raises(CkanApiError):
            client.package_list()

    def test_raises_on_http_error(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(500, {})
        with pytest.raises(CkanApiError):
            client.package_list()

    def test_raises_on_non_list_result(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(200, {"success": True, "result": {}})
        with pytest.raises(CkanApiError):
            client.package_list()

    def test_raises_on_non_dict_payload(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(200, ["not", "a", "dict"])
        with pytest.raises(CkanApiError):
            client.package_list()

    def test_raises_on_connection_error(self):
        import requests

        client = CkanClient("https://example.org", session=Mock())
        client._session.get.side_effect = requests.exceptions.ConnectionError("dns fail")
        with pytest.raises(CkanConnectionError):
            client.package_list()

    def test_rejects_non_https_base_url(self):
        client = CkanClient("http://example.org", session=Mock())
        with pytest.raises(UnsafeUrlError):
            client.package_list()

    def test_rejects_loopback_base_url(self):
        client = CkanClient("https://127.0.0.1", session=Mock())
        with pytest.raises(UnsafeUrlError):
            client.package_list()


class TestListResources:
    def test_parses_resources_and_skips_incomplete_entries(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(
            200,
            {
                "success": True,
                "result": {
                    "resources": [
                        {
                            "id": "r1",
                            "url": "https://example.org/r1.csv",
                            "name": "Recurso 1",
                            "format": "csv",
                            "last_modified": "2026-08-01T00:00:00",
                        },
                        {"id": "r2"},  # sem url -> deve ser ignorado
                        {"url": "https://example.org/r3.csv"},  # sem id -> ignorado
                        "not-a-dict",  # entrada malformada -> ignorada
                    ]
                },
            },
        )
        resources = client.list_resources("pkg-1")
        assert len(resources) == 1
        assert resources[0].resource_id == "r1"
        assert resources[0].package_id == "pkg-1"
        assert resources[0].format == "CSV"

    def test_raises_on_malformed_resources_field(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(
            200, {"success": True, "result": {"resources": "not-a-list"}}
        )
        with pytest.raises(CkanApiError):
            client.list_resources("pkg-1")

    def test_skips_and_survives_resources_with_wrong_field_types(self):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _json_response(
            200,
            {
                "success": True,
                "result": {
                    "resources": [
                        {"id": "r1", "url": 12345},  # url não-string -> ignorado
                        {"id": ["r2"], "url": "https://example.org/r2.csv"},  # id não-string -> ignorado
                        {
                            "id": "r3",
                            "url": "https://example.org/r3.csv",
                            "format": 7,  # tipo inesperado -> não deve quebrar .upper()
                            "name": None,
                        },
                    ]
                },
            },
        )
        resources = client.list_resources("pkg-1")
        assert len(resources) == 1
        assert resources[0].resource_id == "r3"
        assert resources[0].format == "7"
        assert resources[0].name == "r3"  # cai no fallback (name ausente/None)


def _sample_resource(url: str = "https://example.org/r1.csv") -> ResourceMetadata:
    return ResourceMetadata(
        resource_id="r1",
        package_id="pkg-1",
        name="Recurso 1.csv",
        url=url,
        format="CSV",
        last_modified=None,
        raw={},
    )


class TestDownloadResource:
    def test_writes_file_and_records_hash_and_size(self, tmp_path: Path):
        client = CkanClient("https://example.org", session=Mock())
        content = b"col_a,col_b\n1,2\n"
        client._session.get.return_value = _streaming_response(
            200, [content[:5], content[5:]], headers={"Content-Type": "text/csv"}
        )

        record = client.download_resource(_sample_resource(), tmp_path)

        assert record.dest_path.exists()
        assert record.dest_path.read_bytes() == content
        assert record.sha256 == hashlib.sha256(content).hexdigest()
        assert record.size_bytes == len(content)
        assert record.content_type == "text/csv"
        assert record.collected_at
        # nenhum arquivo temporário deve sobrar
        assert list(tmp_path.glob("*.part")) == []

    def test_raises_on_http_error(self, tmp_path: Path):
        client = CkanClient("https://example.org", session=Mock())
        client._session.get.return_value = _streaming_response(404, [])
        with pytest.raises(CkanApiError):
            client.download_resource(_sample_resource(), tmp_path)

    def test_rejects_non_https_resource_url(self, tmp_path: Path):
        client = CkanClient("https://example.org", session=Mock())
        with pytest.raises(UnsafeUrlError):
            client.download_resource(_sample_resource(url="http://example.org/r1.csv"), tmp_path)

    def test_rejects_download_exceeding_declared_content_length(self, tmp_path: Path):
        client = CkanClient("https://example.org", session=Mock(), max_download_bytes=10)
        client._session.get.return_value = _streaming_response(
            200, [b"x" * 20], headers={"Content-Length": "20"}
        )
        with pytest.raises(CkanApiError):
            client.download_resource(_sample_resource(), tmp_path)
        assert list(tmp_path.glob("*.part")) == []

    def test_rejects_download_exceeding_limit_without_content_length(self, tmp_path: Path):
        client = CkanClient("https://example.org", session=Mock(), max_download_bytes=10)
        client._session.get.return_value = _streaming_response(200, [b"x" * 6, b"y" * 6])
        with pytest.raises(CkanApiError):
            client.download_resource(_sample_resource(), tmp_path)
        assert list(tmp_path.glob("*.part")) == []
        assert list(tmp_path.glob("*")) == []

    def test_does_not_clobber_existing_file_on_failed_download(self, tmp_path: Path):
        client = CkanClient("https://example.org", session=Mock())
        resource = _sample_resource()
        dest_dir = tmp_path

        # primeiro download bem-sucedido
        client._session.get.return_value = _streaming_response(200, [b"original"])
        first = client.download_resource(resource, dest_dir)
        assert first.dest_path.read_bytes() == b"original"

        # segundo download falha no meio -> arquivo original deve permanecer intacto
        failing_response = _streaming_response(200, [b"partial"])
        failing_response.iter_content.side_effect = ConnectionError("dropped")
        client._session.get.return_value = failing_response
        with pytest.raises(Exception):
            client.download_resource(resource, dest_dir)

        assert first.dest_path.read_bytes() == b"original"
        assert list(dest_dir.glob("*.part")) == []

    def test_mid_stream_network_failure_raises_connection_error(self, tmp_path: Path):
        import requests

        client = CkanClient("https://example.org", session=Mock())
        response = _streaming_response(200, [])
        response.iter_content.side_effect = requests.exceptions.ChunkedEncodingError("truncated")
        client._session.get.return_value = response

        with pytest.raises(CkanConnectionError):
            client.download_resource(_sample_resource(), tmp_path)
        assert list(tmp_path.glob("*.part")) == []
