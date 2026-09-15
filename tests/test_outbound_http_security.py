from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from collector.adapters import (
    _SafeRedirectHandler,
    _allowed_hosts,
    _http_get,
    extract_html_links,
)


class _Response:
    def __init__(self, payload: bytes, *, url: str = "https://example.gov.br/data", headers=None):
        self._payload = payload
        self._url = url
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def geturl(self):
        return self._url

    def read(self, size=-1):
        if size is None or size < 0:
            return self._payload
        return self._payload[:size]


class _Opener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout=None):
        self.calls.append((request, timeout))
        return self.response


class OutboundHttpSecurityTests(unittest.TestCase):
    @patch("collector.adapters.build_opener")
    def test_cleartext_is_rejected_before_network(self, build_opener):
        with self.assertRaises(ValueError):
            _http_get("http://example.gov.br/data")
        build_opener.assert_not_called()

    @patch("collector.adapters.build_opener")
    def test_unapproved_host_is_rejected_before_network(self, build_opener):
        with self.assertRaisesRegex(ValueError, "host outbound não autorizado"):
            _http_get(
                "https://evil.example/data",
                allowed_hosts={"example.gov.br"},
            )
        build_opener.assert_not_called()

    @patch("collector.adapters.build_opener")
    def test_payload_size_is_bounded_even_without_content_length(self, build_opener):
        build_opener.return_value = _Opener(_Response(b"x" * 2049))
        with self.assertRaisesRegex(ValueError, "excede limite"):
            _http_get(
                "https://example.gov.br/data",
                allowed_hosts={"example.gov.br"},
                max_bytes=2048,
            )

    @patch("collector.adapters.build_opener")
    def test_declared_oversized_payload_is_rejected(self, build_opener):
        build_opener.return_value = _Opener(
            _Response(b"small", headers={"Content-Length": "999999"})
        )
        with self.assertRaisesRegex(ValueError, "excede limite"):
            _http_get(
                "https://example.gov.br/data",
                allowed_hosts={"example.gov.br"},
                max_bytes=2048,
            )

    def test_sensitive_header_cannot_follow_cross_host_redirect(self):
        handler = _SafeRedirectHandler({"example.gov.br", "cdn.example.gov.br"})
        request = Request(
            "https://example.gov.br/data",
            headers={"Authorization": "Bearer secret"},
        )
        with self.assertRaises(HTTPError) as caught:
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://cdn.example.gov.br/data",
            )
        self.assertIn("sensitive headers", str(caught.exception))

    def test_host_options_reject_url_shaped_allowlist_entries(self):
        with self.assertRaisesRegex(ValueError, "host inválido"):
            _allowed_hosts(
                "https://example.gov.br/data",
                {"allowed_hosts": ["https://evil.example/path"]},
            )

    def test_html_link_extraction_drops_non_https_targets(self):
        links = extract_html_links(
            '<a href="/ok">ok</a><a href="http://evil.example/x">bad</a>',
            "https://example.gov.br/base/",
        )
        self.assertEqual(links, ["https://example.gov.br/ok"])


if __name__ == "__main__":
    unittest.main()
