from __future__ import annotations

import unittest

from collector.comexstat_api import ComexStatApiClient, soybean_export_payload


class _Response:
    def __init__(self, *, url: str, payload: dict, status: int = 200) -> None:
        self.url = url
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _Session:
    def __init__(self) -> None:
        self.headers = {}
        self.last = None

    def get(self, url, **kwargs):
        self.last = ("GET", url, kwargs)
        if url.endswith("/general/dates/updated"):
            return _Response(url=url, payload={"success": True, "data": {"updated": "2026-08-06", "year": "2026", "monthNumber": "07"}})
        return _Response(url=url, payload={"success": True, "data": {"min": "1997", "max": "2026"}})

    def post(self, url, **kwargs):
        self.last = ("POST", url, kwargs)
        return _Response(url=url, payload={"success": True, "data": {"list": []}})


class ComexStatApiTests(unittest.TestCase):
    def test_host_is_locked(self) -> None:
        with self.assertRaises(ValueError):
            ComexStatApiClient(base_url="https://example.com", session=_Session())
        with self.assertRaises(ValueError):
            ComexStatApiClient(base_url="http://api-comexstat.mdic.gov.br", session=_Session())

    def test_metadata_endpoints(self) -> None:
        client = ComexStatApiClient(session=_Session())
        update = client.last_update()
        self.assertEqual((update.year, update.month), (2026, 7))
        self.assertEqual(client.available_years(), (1997, 2026))

    def test_soy_payload_preserves_ncm_scope(self) -> None:
        payload = soybean_export_payload(start="2026-07", end="2026-07")
        self.assertEqual(payload["flow"], "export")
        self.assertEqual(payload["filters"][0]["filter"], "ncm")
        self.assertEqual(payload["filters"][0]["values"], [12011000, 12019000])
        self.assertEqual(payload["details"], ["ncm", "state"])
        self.assertNotIn("city", payload["details"])

    def test_invalid_query_is_blocked(self) -> None:
        client = ComexStatApiClient(session=_Session())
        with self.assertRaises(ValueError):
            client.general({"flow": "export", "period": {}, "filters": [], "details": [], "metrics": []})

    def test_redirect_to_other_host_is_blocked(self) -> None:
        class RedirectSession(_Session):
            def get(self, url, **kwargs):
                return _Response(url="https://example.com/data", payload={"success": True, "data": {}})
        client = ComexStatApiClient(session=RedirectSession())
        with self.assertRaises(RuntimeError):
            client.last_update()


if __name__ == "__main__":
    unittest.main()
