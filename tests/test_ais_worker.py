import unittest

from collector.ais_worker import AisBatchSink
from models.port_geofence import PortZone


class FakeStore:
    def __init__(self):
        self.rows = []

    def load_ais(self, rows):
        self.rows.extend(rows)
        return len(rows)


class AisWorkerTest(unittest.TestCase):
    def test_batch_sink_preserves_raw_and_applies_geofence(self):
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
        sink = AisBatchSink(store=store, zones=[zone], batch_size=1)
        sink({
            "message_type": "PositionReport",
            "mmsi": "710123456",
            "imo": "9876543",
            "vessel_name": "AGRO STAR",
            "observed_at": "2026-08-26T10:00:00+00:00",
            "latitude": -24.0,
            "longitude": -46.30,
            "sog_kn": 0.1,
            "source_id": "aisstream",
            "_raw_message": {"MessageType": "PositionReport", "MetaData": {"MMSI": 710123456}},
        })
        self.assertEqual(len(store.rows), 1)
        row = store.rows[0]
        self.assertEqual(row["port_id"], "SANTOS")
        self.assertEqual(row["terminal_id"], "T1")
        self.assertEqual(row["zone"], "BERTH")
        self.assertIn("PositionReport", row["raw_message_json"])
        self.assertTrue(row["observation_id"])

    def test_flush_empty(self):
        store = FakeStore()
        sink = AisBatchSink(store=store, zones=[], batch_size=10)
        self.assertEqual(sink.flush(), 0)


if __name__ == "__main__":
    unittest.main()
