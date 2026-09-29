from __future__ import annotations

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
            "conab_safra_graos_xlsx", "imea_operational_xlsx", "ibge_pam", "cepea_prices",
            "mdic_comexstat", "antt_open_data", "anp_diesel", "aneel_siga", "ons_open_data",
            "abiove_processing", "sigsif_cattle", "bcb_ptax_usd_daily", "ana_hidroweb",
            "inmet_weather", "cptec_weather", "usda_wasde", "usda_nass_quickstats",
            "usda_crop_progress", "usda_crop_production", "usda_acreage",
            "usda_prospective_plantings", "usda_grain_stocks", "usda_fas_export_sales",
            "usda_fas_psd", "usda_weekly_weather_crop_bulletin", "noaa_cpc",
            "sagyp_argentina", "bcr_gea", "bolsa_cereales_argentina",
            "amis_market_monitor", "igc_global", "faostat", "aisstream_maritime",
            "nasa_cmr_stac_lpcloud",
            "antt_rntrc", "antt_mdfe_public", "epe_sienergia_biomass", "ibge_pevs_biomass",
            "snif_forest_biomass", "sema_mt_sisflora", "ons_biomass_generation", "epe_ben_biomass",
            "anp_biometano", "ibama_dof_native", "whatsapp_freight_authorized",
        }
        self.assertTrue(required.issubset(registry.entries))
        self.assertTrue(registry.by_domain("us_crop"))
        self.assertTrue(registry.by_domain("argentina_crop"))
        self.assertTrue(registry.by_domain("global_market"))

    def test_nasa_cmr_stac_is_registered_but_gated(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        source = registry.get("nasa_cmr_stac_lpcloud")
        self.assertEqual(source.domain, "geospatial")
        self.assertEqual(source.method, "STAC")
        self.assertEqual(source.status, "gated")
        self.assertTrue(source.trusted_transport)
        decision = registry.decision("nasa_cmr_stac_lpcloud")
        self.assertFalse(decision.due)
        self.assertEqual(decision.reason, "status:gated")

    def test_active_source_rejects_insecure_transport(self) -> None:
        payload = {
            "source_id": "unsafe_source", "name": "Unsafe", "domain": "news", "type": "web",
            "endpoint": "http://example.invalid/data", "method": "HTML", "frequency": "daily",
            "freshness_expected": "daily", "last_collection_at": None, "status": "active",
            "fallback": [], "license": "test", "reliability": "unknown", "trusted_transport": False,
        }
        with self.assertRaisesRegex(ValueError, "unsafe endpoint"):
            RegistryEntry.from_dict(payload)

    def test_due_respects_interval_and_retry_backoff(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        source = "bcb_ptax_usd_daily"

        self.assertTrue(registry.decision(source, state={}, now=now).due)
        fresh = registry.decision(
            source,
            state={"last_checked_at": "2026-09-14T17:30:00+00:00", "consecutive_failures": 0},
            now=now,
        )
        self.assertFalse(fresh.due)
        self.assertEqual(fresh.reason, "fresh_enough")

        retry = registry.decision(
            source,
            state={"last_checked_at": "2026-09-14T17:00:00+00:00", "consecutive_failures": 1},
            now=now,
        )
        self.assertFalse(retry.due)
        self.assertEqual(retry.reason, "retry_backoff")

    def test_health_overlay_uses_runtime_state_without_mutating_registry(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        source_id = "bcb_ptax_usd_daily"
        static = registry.get(source_id)
        self.assertIsNone(static.last_collection_at)

        state = {"last_checked_at": "2026-09-14T17:00:00+00:00", "consecutive_failures": 0}
        health = registry.health(source_id, state=state, now=now)
        self.assertEqual(health.status, "HEALTHY")
        self.assertFalse(health.alert)

        view = registry.operational_view(source_id, state=state, now=now)
        self.assertEqual(view["source"]["last_collection_at"], "2026-09-14T17:00:00+00:00")
        self.assertEqual(view["health"]["status"], "HEALTHY")
        self.assertIsNone(registry.get(source_id).last_collection_at)

    def test_health_flags_never_collected_stale_and_degraded(self) -> None:
        registry = DataSourceRegistry.load(REGISTRY)
        now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
        source_id = "bcb_ptax_usd_daily"

        self.assertEqual(registry.health(source_id, state={}, now=now).status, "NEVER_COLLECTED")
        stale = registry.health(
            source_id,
            state={"last_checked_at": "2026-09-13T00:00:00+00:00", "consecutive_failures": 0},
            now=now,
        )
        self.assertEqual(stale.status, "STALE")
        self.assertTrue(stale.alert)
        degraded = registry.health(
            source_id,
            state={"last_checked_at": "2026-09-14T17:00:00+00:00", "consecutive_failures": 1},
            now=now,
        )
        self.assertEqual(degraded.status, "DEGRADED")
        self.assertTrue(degraded.alert)

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
            "source_id": "a_source", "name": "A source", "domain": "news", "type": "web",
            "endpoint": "https://example.invalid/a", "method": "HTML", "frequency": "daily",
            "freshness_expected": "daily", "last_collection_at": None, "status": "active",
            "fallback": ["missing_source"], "license": "test", "reliability": "unknown",
            "trusted_transport": True,
        })
        with self.assertRaisesRegex(ValueError, "unknown fallback"):
            DataSourceRegistry([base])


if __name__ == "__main__":
    unittest.main()
