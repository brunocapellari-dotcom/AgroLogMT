from __future__ import annotations

import unittest

from collector.transport_security import validate_https_url, validate_same_https_host


class TransportSecurityTests(unittest.TestCase):
    def test_accepts_standard_https(self) -> None:
        self.assertEqual(
            validate_https_url("https://example.gov.br/data", allowed_hosts={"example.gov.br"}),
            "https://example.gov.br/data",
        )

    def test_rejects_non_https_schemes(self) -> None:
        for value in (
            "http://example.gov.br/data",
            "file:///etc/passwd",
            "ftp://example.gov.br/data",
            "gopher://example.gov.br/",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_https_url(value)

    def test_rejects_embedded_credentials(self) -> None:
        with self.assertRaises(ValueError):
            validate_https_url("https://user:secret@example.gov.br/data")

    def test_rejects_nonstandard_port(self) -> None:
        with self.assertRaises(ValueError):
            validate_https_url("https://example.gov.br:8443/data")

    def test_rejects_host_outside_allowlist(self) -> None:
        with self.assertRaises(ValueError):
            validate_https_url(
                "https://attacker.example/data",
                allowed_hosts={"example.gov.br"},
            )

    def test_same_host_redirect_guard(self) -> None:
        self.assertEqual(
            validate_same_https_host(
                "https://example.gov.br/redirected",
                "https://example.gov.br/original",
            ),
            "https://example.gov.br/redirected",
        )
        with self.assertRaises(ValueError):
            validate_same_https_host(
                "https://other.example/redirected",
                "https://example.gov.br/original",
            )


if __name__ == "__main__":
    unittest.main()
