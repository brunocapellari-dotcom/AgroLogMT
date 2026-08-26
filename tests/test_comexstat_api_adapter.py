from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from collector.adapters import ComexStatApiAdapter
from collector.comexstat_api import ComexUpdate
from collector.models import SourceSpec


class _FakeClient:
    base_url = "https://api-comexstat.mdic.gov.br"
    last_payload = None
    last_module = None

    def __init__(self, *, timeout=120):
        self.timeout = timeout

    def last_update(self):
        return ComexUpdate(updated="2026-08-06", year=2026, month=7)

    def query(self, payload, *, module="general"):
        type(self).last_payload = payload
        type(self).last_module = module
        return {"success": True, "data": {"list": [{"monthNumber": 7, "metricFOB": 10}]}}


class ComexStatApiAdapterTests(unittest.TestCase):
    def _spec(self, **overrides):
        options = {
            "module": "general",
            "period_mode": "latest_complete_month",
            "flow": "export",
            "month_detail": True,
            "filters": [
                {"filter": "ncm", "values": [12011000, 12019000]},
                {"filter": "state", "values": [51]},
            ],
            "details": ["ncm", "state", "country", "via", "urf"],
            "metrics": ["metricFOB", "metricKG"],
        }
        options.update(overrides.pop("options", {}))
        return SourceSpec(
            source_id="mdic_comexstat_soja_mt_export_api",
            name="MDIC ComexStat API - Soja MT export",
            group="dados",
            method="comexstat_api",
            expected_frequency="monthly",
            file_extension="json",
            options=options,
            **overrides,
        )

    @patch("collector.adapters.ComexStatApiClient", _FakeClient)
    def test_latest_published_competence_drives_query(self):
        result = ComexStatApiAdapter().fetch(self._spec())
        self.assertEqual(_FakeClient.last_payload["period"], {"from": "2026-07", "to": "2026-07"})
        self.assertEqual(_FakeClient.last_payload["filters"][1], {"filter": "state", "values": [51]})
        self.assertEqual(_FakeClient.last_module, "general")
        self.assertEqual(result.content_type, "application/json")
        self.assertEqual(result.last_modified, "2026-08-06")
        parsed = json.loads(result.payload)
        self.assertTrue(parsed["success"])

    @patch("collector.adapters.ComexStatApiClient", _FakeClient)
    def test_unapproved_period_mode_is_blocked(self):
        with self.assertRaises(ValueError):
            ComexStatApiAdapter().fetch(self._spec(options={"period_mode": "current_month"}))

    @patch("collector.adapters.ComexStatApiClient", _FakeClient)
    def test_cities_module_is_supported_explicitly(self):
        ComexStatApiAdapter().fetch(self._spec(options={"module": "cities", "details": ["country", "state", "city", "heading"]}))
        self.assertEqual(_FakeClient.last_module, "cities")


if __name__ == "__main__":
    unittest.main()
