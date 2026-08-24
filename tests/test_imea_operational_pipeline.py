from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from collector.imea_operational_pipeline import resolve_file_id, run_imea_operational_pipeline
from collector.models import SourceSpec


class _FakeStore:
    project_id = "test-project"
    bq_location = "southamerica-east1"
    bq = object()
    drive = object()

    def __init__(self) -> None:
        self.manifests = []
        self.states = []

    def store_raw(self, spec, payload, sha256, collected_at=None):
        return SimpleNamespace(path="drive://raw-copy", sha256=sha256, size=len(payload))

    def write_manifest(self, manifest):
        self.manifests.append(manifest)
        return "bigquery://manifest"

    def save_state(self, source_id, state):
        self.states.append((source_id, state))
        return "bigquery://state"


def _spec() -> SourceSpec:
    return SourceSpec(
        source_id="imea_operational_xlsx",
        name="IMEA workbook",
        group="dados",
        method="drive_workbook",
        enabled=False,
        file_extension="xlsx",
        evidence_class="observado",
        options={"file_id_env": "AGROLOG_IMEA_FILE_ID"},
    )


class ImeaOperationalPipelineTests(unittest.TestCase):
    def test_file_id_must_come_from_environment_and_is_not_a_url(self) -> None:
        self.assertEqual(resolve_file_id(_spec(), {"AGROLOG_IMEA_FILE_ID": "abcDEF_123"}), "abcDEF_123")
        with self.assertRaises(ValueError):
            resolve_file_id(_spec(), {})
        with self.assertRaises(ValueError):
            resolve_file_id(_spec(), {"AGROLOG_IMEA_FILE_ID": "https://drive.google.com/file/d/x"})

    @patch("collector.imea_operational_pipeline.ImeaOperationalBigQueryLoader")
    @patch("collector.imea_operational_pipeline.parse_workbook")
    @patch("collector.imea_operational_pipeline._drive_download")
    def test_pipeline_preserves_raw_manifest_and_routes_canonical_groups(self, download, parser, loader_cls) -> None:
        download.return_value = (
            b"xlsx-bytes",
            {"name": "imea-1.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "modifiedTime": "2026-08-24T20:00:00Z"},
        )
        parser.return_value = {
            "records": [{"record_id": "r1"}],
            "qa": {"records": 1, "first_date": "2023-01-01", "last_date": "2026-08-22", "natural_key_duplicates": 0, "progress_out_of_range": 0},
        }
        loader = loader_cls.return_value
        loader.load.return_value = {
            "indicators": {"status": "loaded", "records_inserted": 1},
            "freight": {"status": "empty", "records_inserted": 0},
            "progress": {"status": "empty", "records_inserted": 0},
        }
        store = _FakeStore()
        code, payload = run_imea_operational_pipeline(_spec(), store, file_id="authorized-file")
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "loaded")
        self.assertEqual(payload["raw_artifact_ref"], "drive://raw-copy")
        self.assertEqual(len(store.manifests), 1)
        self.assertEqual(store.manifests[0].observed_url, "drive://authorized-file")
        self.assertEqual(store.manifests[0].extra["row_level_evidence"], "mixed_observed_and_estimated")
        self.assertEqual(store.states[0][0], "imea_operational_xlsx")
        loader.load.assert_called_once()

    def test_source_is_registered_but_disabled_by_default(self) -> None:
        config = json.loads(Path("collector/config/sources.pilot.json").read_text(encoding="utf-8"))
        source = next(item for item in config["sources"] if item["source_id"] == "imea_operational_xlsx")
        self.assertFalse(source["enabled"])
        self.assertEqual(source["options"]["file_id_env"], "AGROLOG_IMEA_FILE_ID")
        self.assertNotIn("file_id", source["options"])


if __name__ == "__main__":
    unittest.main()
