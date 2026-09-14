from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from collector.adapters import AcquisitionResult
from collector.gaps import detect_gaps
from collector.models import SourceSpec
from collector.orchestrator import CollectorEngine
from collector.storage import LocalStore, sha256_bytes


class FakeAdapter:
    def __init__(self, payload: bytes, raw_payload: bytes | None = None) -> None:
        self.payload = payload
        self.raw_payload = raw_payload

    def fetch(self, spec: SourceSpec) -> AcquisitionResult:
        return AcquisitionResult(
            payload=self.payload,
            raw_payload=self.raw_payload,
            observed_url=spec.url or "memory://fixture",
            content_type="text/csv",
        )


class CollectorCoreTests(unittest.TestCase):
    def test_idempotency_by_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = SourceSpec(source_id="fixture", name="Fixture", group="dados", method="fake", url="memory://fixture", file_extension="csv")
            engine = CollectorEngine(LocalStore(tmp), adapter_resolver=lambda _: FakeAdapter(b"a,b\n1,2\n"))
            first = engine.run_source(spec)
            second = engine.run_source(spec)
            self.assertEqual(first.status, "updated")
            self.assertTrue(first.changed)
            self.assertEqual(second.status, "unchanged")
            self.assertFalse(second.changed)
            raw_files = list((Path(tmp) / "raw").rglob("*.csv"))
            self.assertEqual(len(raw_files), 1)

    def test_machine_native_raw_controls_hash_storage_but_parse_payload_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parse_payload = b'{"latest":{"value":1}}'
            source_raw = b"220;A;USD;5,0912;5,0918;1,0000;1,0000\n"
            spec = SourceSpec(source_id="raw-fixture", name="RAW Fixture", group="dados", method="fake", file_extension="csv")
            engine = CollectorEngine(LocalStore(tmp), adapter_resolver=lambda _: FakeAdapter(parse_payload, raw_payload=source_raw))
            outcome = engine.run_source_capture(spec)

            self.assertEqual(outcome.payload, parse_payload)
            self.assertEqual(outcome.manifest.sha256, sha256_bytes(source_raw))
            self.assertEqual(outcome.manifest.bytes_read, len(source_raw))
            raw_files = list((Path(tmp) / "raw").rglob("*.csv"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].read_bytes(), source_raw)

    def test_business_daily_gap(self) -> None:
        missing = detect_gaps(
            observed=["2026-08-17", "2026-08-19", "2026-08-20", "2026-08-21"],
            start="2026-08-17",
            end="2026-08-23",
            frequency="business_daily",
        )
        self.assertEqual(missing, ["2026-08-18"])

    def test_monthly_gap(self) -> None:
        missing = detect_gaps(
            observed=["2026-01", "2026-02", "2026-04"],
            start="2026-01-01",
            end="2026-04-30",
            frequency="monthly",
        )
        self.assertEqual(missing, ["2026-03"])

    def test_manifest_written_on_error(self) -> None:
        class BrokenAdapter:
            def fetch(self, spec: SourceSpec) -> AcquisitionResult:
                raise RuntimeError("falha artificial")

        with tempfile.TemporaryDirectory() as tmp:
            spec = SourceSpec(source_id="broken", name="Broken", group="radar", method="broken")
            engine = CollectorEngine(LocalStore(tmp), adapter_resolver=lambda _: BrokenAdapter())
            manifest = engine.run_source(spec)
            self.assertEqual(manifest.status, "error")
            files = list((Path(tmp) / "manifests").rglob("*.json"))
            self.assertEqual(len(files), 1)
            saved = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertIn("falha artificial", saved["error"])


if __name__ == "__main__":
    unittest.main()
