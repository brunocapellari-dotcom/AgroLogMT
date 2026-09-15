import json
import unittest
from pathlib import Path


class MaritimeSourceRegistryTests(unittest.TestCase):
    def setUp(self):
        path = Path("collector/config/maritime_source_registry.v1.json")
        self.payload = json.loads(path.read_text(encoding="utf-8"))

    def test_required_source_families_are_registered(self):
        ids = {row["source_id"] for row in self.payload["sources"]}
        self.assertTrue({
            "aisstream_live",
            "pyais_decoder",
            "antaq_estatistico_aquaviario",
            "official_lineups",
            "official_port_terminals",
            "comexstat_trade",
            "chm_pnboia",
            "chm_meteocean_forecast",
            "chm_bndo_authorized_data",
            "maritime_weather",
            "authorized_hydrography",
            "port_geofences",
        }.issubset(ids))

    def test_ais_stream_has_operational_resilience_contract(self):
        source = next(row for row in self.payload["sources"] if row["source_id"] == "aisstream_live")
        self.assertEqual(source["credential_class"], "SECRET_MANAGER_ONLY")
        self.assertEqual(
            set(source["health_required"]),
            {"heartbeat", "retry", "reconnect", "checkpoint", "deduplication"},
        )
        self.assertEqual(source["checkpoint_semantics"], "LOGICAL_CHECKPOINT_ONLY_NO_UPSTREAM_REPLAY")

    def test_hydrography_is_rights_gated(self):
        for source_id in ("authorized_hydrography", "chm_bndo_authorized_data"):
            source = next(row for row in self.payload["sources"] if row["source_id"] == source_id)
            self.assertEqual(source["runtime_status"], "RIGHTS_GATED")
            self.assertTrue(source["commercial_use_requires_rights_review"])

    def test_programming_single_ais_weather_and_trade_are_fail_closed(self):
        rules = self.payload["rules"]
        self.assertTrue(rules["programming_is_not_realized"])
        self.assertTrue(rules["single_ais_message_never_confirms_physical_state"])
        self.assertTrue(rules["weather_does_not_imply_port_restriction_without_authorized_rule"])
        self.assertTrue(rules["aggregate_trade_data_never_implies_vessel_level_cargo"])

    def test_trade_sources_forbid_vessel_level_attribution(self):
        for source_id in ("antaq_estatistico_aquaviario", "comexstat_trade"):
            source = next(row for row in self.payload["sources"] if row["source_id"] == source_id)
            self.assertFalse(source["vessel_level_attribution_allowed"])


if __name__ == "__main__":
    unittest.main()
