from __future__ import annotations

import unittest

from collector.comexstat_api import ComexStatApiClient, soybean_export_payload, trade_payload


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
        if url.endswith("/general/dates/years"):
            return _Response(url=url, payload={"success": True, "data": {"min": "1997", "max": "2026"}})
        return _Response(url=url, payload={"success": True, "data": {"list": []}})

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
        self.assertEqual(update.competence, "2026-07")
        self.assertEqual(client.available_years(), (1997, 2026))

    def test_soy_payload_preserves_mt_ncm_and_logistics_scope(self) -> None:
        payload = soybean_export_payload(start="2026-07", end="2026-07", state_code=51)
        self.assertEqual(payload["flow"], "export")
        self.assertEqual(payload["filters"][0], {"filter": "ncm", "values": [12011000, 12019000]})
        self.assertEqual(payload["filters"][1], {"filter": "state", "values": [51]})
        self.assertEqual(payload["details"], ["ncm", "state", "country", "via", "urf"])
        self.assertNotIn("city", payload["details"])

    def test_trade_payload_rejects_empty_metrics(self) -> None:
        with self.assertRaises(ValueError):
            trade_payload(
                flow="export", start="2026-07", end="2026-07",
                filters=[], details=[], metrics=[],
            )

    def test_invalid_query_is_blocked(self) -> None:
        client = ComexStatApiClient(session=_Session())
        with self.assertRaises(ValueError):
            client.general({"flow": "export", "period": {}, "filters": [], "details": [], "metrics": []})

    def test_redirect_is_blocked_even_on_same_host(self) -> None:
        class RedirectSession(_Session):
            def get(self, url, **kwargs):
                return _Response(url=url, payload={"success": True, "data": {}}, status=302)
        client = ComexStatApiClient(session=RedirectSession())
        with self.assertRaises(RuntimeError):
            client.last_update()

    def test_other_host_response_is_blocked(self) -> None:
        class RedirectSession(_Session):
            def get(self, url, **kwargs):
                return _Response(url="https://example.com/data", payload={"success": True, "data": {}})
        client = ComexStatApiClient(session=RedirectSession())
        with self.assertRaises(RuntimeError):
            client.last_update()

    def test_data_list_accepts_documented_shape(self) -> None:
        rows = ComexStatApiClient.data_list({"success": True, "data": {"list": [{"ncm": "1201"}]}})
        self.assertEqual(rows, [{"ncm": "1201"}])

    def test_data_list_accepts_legacy_nested_data_shape(self) -> None:
        rows = ComexStatApiClient.data_list({"success": True, "data": {"data": [{"state": "Mato Grosso"}]}})
        self.assertEqual(rows, [{"state": "Mato Grosso"}])


if __name__ == "__main__":
    unittest.main()
