import hashlib
import unittest

from collector.ais_worker import AisBatchSink
from models.port_geofence import PortZone


class FakeStore:
    def __init__(self):
        self.rows = []
        self.checkpoints = []

    @staticmethod
    def stable_id(*parts):
        return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()

    def load_ais(self, rows):
        self.rows.extend(rows)
        return len(rows)

    def load_stream_checkpoint(self, row):
        self.checkpoints.append(row)
        return 1


class AisWorkerTest(unittest.TestCase):
    def test_batch_sink_preserves_raw_and_requires_corroboration_for_geofence(self):
        zone = PortZone(
            zone_id="SANTOS-T1",
            port_id="SANTOS",
            zone="BERTH",
            terminal_id="T1",
            geofence_version="2026-08-26",
            source_id="fixture",
            polygon=((-24.05, -46.35), (-24.05, -46.25), (-23.95, -46.25), (-23.95, -46.35)),
        )
        store = FakeStore()
        sink = AisBatchSink(store=store, zones=[zone], run_id="run-1", batch_size=1)
        common = {
            "message_type": "PositionReport",
            "mmsi": "710123456",
            "imo": "9074729",
            "vessel_name": "AGRO STAR",
            "latitude": -24.0,
            "longitude": -46.30,
            "sog_kn": 0.1,
            "source_id": "aisstream",
            "_raw_message": {"MessageType": "PositionReport", "MetaData": {"MMSI": 710123456}},
        }
        sink({**common, "observed_at": "2026-08-26T10:00:00+00:00"})
        sink({**common, "observed_at": "2026-08-26T10:01:00+00:00"})

        self.assertEqual(len(store.rows), 2)
        first, second = store.rows
        self.assertEqual(first["quality_status"], "UNCONFIRMED_SINGLE")
        self.assertFalse(first["corroborated"])
        self.assertIsNone(first["port_id"])
        self.assertEqual(first["zone"], "SEA")
        self.assertEqual(second["quality_status"], "CONFIRMED_SEQUENCE")
        self.assertTrue(second["corroborated"])
        self.assertEqual(second["port_id"], "SANTOS")
        self.assertEqual(second["terminal_id"], "T1")
        self.assertEqual(second["zone"], "BERTH")
        self.assertIn("PositionReport", second["raw_message_json"])
        self.assertTrue(second["observation_id"])
        self.assertTrue(store.checkpoints)
        self.assertFalse(store.checkpoints[-1]["replay_capable"])

    def test_deduplicates_same_message_within_capture_window(self):
        store = FakeStore()
        sink = AisBatchSink(store=store, zones=[], run_id="run-2", batch_size=10)
        row = {
            "message_type": "PositionReport",
            "mmsi": "710123456",
            "imo": "9074729",
            "observed_at": "2026-08-26T10:00:00+00:00",
            "latitude": -24.0,
            "longitude": -46.30,
            "source_id": "aisstream",
        }
        sink(row)
        sink(dict(row))
        sink.flush()
        self.assertEqual(len(store.rows), 1)
        self.assertEqual(sink.duplicates_suppressed, 1)

    def test_flush_empty(self):
        store = FakeStore()
        sink = AisBatchSink(store=store, zones=[], run_id="run-3", batch_size=10)
        self.assertEqual(sink.flush(), 0)


if __name__ == "__main__":
    unittest.main()
