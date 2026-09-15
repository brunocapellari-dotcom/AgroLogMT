from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from collector.source_registry import DataSourceRegistry, RegistryEntry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "collector" / "config" / "data_source_registry.v1.json"


class DataSourceRegistryTests(unittest.TestCase):
    def test_real_registry_loads_and_contains_official_priority_domains(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        required = {
            "conab_safra_graos_xlsx",
            "imea_operational_xlsx",
            "ibge_pam",
            "cepea_prices",
            "mdic_comexstat",
            "antt_open_data",
            "anp_diesel",
            "aneel_siga",
            "ons_open_data",
            "abiove_processing",
            "sigsif_cattle",
            "bcb_ptax_usd_daily",
            "ana_hidroweb",
            "inmet_weather",
            "cptec_weather",
            "usda_wasde",
            "usda_nass_quickstats",
            "usda_crop_progress",
            "usda_crop_production",
            "usda_acreage",
            "usda_prospective_plantings",
            "usda_grain_stocks",
            "usda_fas_export_sales",
            "usda_fas_psd",
            "usda_weekly_weather_crop_bulletin",
            "noaa_cpc",
            "sagyp_argentina",
            "bcr_gea",
            "bolsa_cereales_argentina",
            "amis_market_monitor",
            "igc_global",
            "faostat",
            "aisstream_maritime",
        }
        self.assertTrue(required.issubset(registry.entries))
        self.assertTrue(registry.by_domain("us_crop"))
        self.assertTrue(registry.by_domain("argentina_crop"))
        self.assertTrue(registry.by_domain("global_market"))

    def test_active_source_rejects_insecure_transport(self) -> None:
        payload = {
            "source_id": "unsafe_source",
            "name": "Unsafe",
            "domain": "news",
            "type": "web",
            "endpoint": "http://example.invalid/data",
            "method": "HTML",
            "frequency": "daily",
            "freshness_expected": "daily",
            "last_collection_at": None,
            "status": "active",
            "fallback": [],
            "license": "test",
            "reliability": "unknown",
            "trusted_transport": False,
        }
        with self.assertRaisesRegex(ValueError, "insecure transport"):
            RegistryEntry.from_dict(payload)

    def test_due_respects_interval_and_retry_backoff(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        source = "bcb_ptax_usd_daily"

        decision = registry.decision(source, state={}, now=now)
        self.assertTrue(decision.due)

        decision = registry.decision(
            source,
            state={"last_checked_at": "2026-09-14T17:30:00+00:00", "consecutive_failures": 0},
            now=now,
        )
        self.assertFalse(decision.due)
        self.assertEqual(decision.reason, "fresh_enough")

        decision = registry.decision(
            source,
            state={"last_checked_at": "2026-09-14T17:00:00+00:00", "consecutive_failures": 1},
            now=now,
        )
        self.assertFalse(decision.due)
        self.assertEqual(decision.reason, "retry_backoff")

    def test_gated_and_planned_sources_never_execute_from_registry(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        for source_id in ("usda_wasde", "sagyp_argentina", "ana_hidroweb"):
            decision = registry.decision(source_id)
            self.assertFalse(decision.due)
            self.assertTrue(decision.reason.startswith("status:"))

    def test_resolve_existing_collector_spec_without_rewriting_it(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        spec = registry.resolve_source_spec("conab_armazens_cadastrados", repo_root=ROOT)
        self.assertEqual(spec.source_id, "conab_armazens_cadastrados")
        self.assertEqual(spec.method, "http")

    def test_unknown_fallback_is_fail_closed(self) -> None:
        base = RegistryEntry.from_dict({
            "source_id": "a_source",
            "name": "A source",
            "domain": "news",
            "type": "web",
            "endpoint": "https://example.invalid/a",
            "method": "HTML",
            "frequency": "daily",
            "freshness_expected": "daily",
            "last_collection_at": None,
            "status": "active",
            "fallback": ["missing_source"],
            "license": "test",
            "reliability": "unknown",
            "trusted_transport": True,
        })
        with self.assertRaisesRegex(ValueError, "unknown fallback"):
            DataSourceRegistry([base])


if __name__ == "__main__":
    unittest.main()
