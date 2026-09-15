from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from collector.registry_scheduler import RegistryScheduler
from collector.source_registry import DataSourceRegistry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "collector" / "config" / "data_source_registry.v1.json"


class MemoryStateStore:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}

    def load_state(self, source_id: str) -> dict:
        return dict(self.data.get(source_id, {}))

    def save_state(self, source_id: str, state: dict) -> str:
        self.data[source_id] = dict(state)
        return f"memory://{source_id}"


class RegistrySchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = DataSourceRegistry.load(REGISTRY)
        self.store = MemoryStateStore()
        self.scheduler = RegistryScheduler(self.registry, self.store, repo_root=ROOT)
        self.now = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)

    def test_existing_conab_collector_is_reused(self) -> None:
        item = self.scheduler.plan_source("conab_armazens_cadastrados", now=self.now)
        self.assertTrue(item.due)
        self.assertEqual(item.execution_source_id, "conab_armazens_cadastrados")
        self.assertIsNotNone(item.spec)
        self.assertEqual(item.spec.method, "http")

    def test_comex_registry_alias_bridges_to_existing_p0_spec(self) -> None:
        item = self.scheduler.plan_source("mdic_comexstat", now=self.now)
        self.assertTrue(item.due)
        self.assertEqual(item.execution_source_id, "mdic_comexstat_soja_mt_export_api")
        self.assertEqual(item.spec.method, "comexstat_api")

    def test_nested_auxiliary_is_not_scheduled_as_duplicate_job(self) -> None:
        item = self.scheduler.plan_source("bcb_olinda_ptax_discovery", now=self.now)
        self.assertFalse(item.due)
        self.assertEqual(item.reason, "nested_auxiliary")
        self.assertIsNone(item.spec)

    def test_record_failure_drives_registry_backoff(self) -> None:
        item = self.scheduler.plan_source("bcb_ptax_usd_daily", now=self.now)
        self.assertTrue(item.due)
        self.scheduler.record_result(item, status="error", error="temporary", at=self.now)
        state = self.store.load_state("bcb_ptax_usd_daily")
        self.assertEqual(state["consecutive_failures"], 1)
        next_item = self.scheduler.plan_source(
            "bcb_ptax_usd_daily",
            now=datetime(2026, 9, 14, 19, 0, tzinfo=timezone.utc),
        )
        self.assertFalse(next_item.due)
        self.assertEqual(next_item.reason, "retry_backoff")

    def test_success_resets_failure_counter(self) -> None:
        item = self.scheduler.plan_source("bcb_ptax_usd_daily", now=self.now)
        self.store.data["bcb_ptax_usd_daily"] = {"consecutive_failures": 3}
        self.scheduler.record_result(item, status="updated", at=self.now)
        self.assertEqual(self.store.data["bcb_ptax_usd_daily"]["consecutive_failures"], 0)

    def test_fallback_candidates_remain_separate_evidence(self) -> None:
        item = self.scheduler.plan_source("mdic_comexstat", now=self.now)
        candidates = self.scheduler.fallback_candidates(item)
        self.assertEqual([candidate.registry_source_id for candidate in candidates], ["mdic_comexstat_bulk"])
        self.assertFalse(candidates[0].due)
        self.assertEqual(candidates[0].reason, "status:gated")


if __name__ == "__main__":
    unittest.main()
