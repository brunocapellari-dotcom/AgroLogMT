import unittest

from collector.lineup_normalizer import normalize_lineup_row
from models.port_geofence import PortZone, classify_position, point_in_polygon


class PortGeofenceAndLineupTest(unittest.TestCase):
    def test_point_in_polygon(self):
        polygon = ((-24.1, -46.4), (-24.1, -46.2), (-23.9, -46.2), (-23.9, -46.4))
        self.assertTrue(point_in_polygon(-24.0, -46.3, polygon))
        self.assertFalse(point_in_polygon(-23.0, -46.3, polygon))

    def test_invalid_geofence_latitude_is_rejected(self):
        with self.assertRaises(ValueError):
            PortZone(
                zone_id="BAD-LAT", port_id="SANTOS", zone="ANCHORAGE",
                polygon=((91.0, -46.4), (-24.1, -46.2), (-23.9, -46.2)),
                geofence_version="2026-08-26", source_id="fixture",
            )

    def test_invalid_geofence_longitude_is_rejected(self):
        with self.assertRaises(ValueError):
            PortZone(
                zone_id="BAD-LON", port_id="SANTOS", zone="BERTH",
                polygon=((-24.1, -181.0), (-24.1, -46.2), (-23.9, -46.2)),
                geofence_version="2026-08-26", source_id="fixture",
            )

    def test_degenerate_geofence_is_rejected(self):
        with self.assertRaises(ValueError):
            PortZone(
                zone_id="BAD-AREA", port_id="SANTOS", zone="BERTH",
                polygon=((-24.0, -46.0), (-24.1, -46.1), (-24.2, -46.2)),
                geofence_version="2026-08-26", source_id="fixture",
            )

    def test_invalid_observation_coordinate_is_rejected(self):
        polygon = ((-24.1, -46.4), (-24.1, -46.2), (-23.9, -46.2), (-23.9, -46.4))
        zone = PortZone(
            zone_id="SANTOS-ANCH-1", port_id="SANTOS", zone="ANCHORAGE",
            polygon=polygon, geofence_version="2026-08-26", source_id="fixture",
        )
        with self.assertRaises(ValueError):
            classify_position(-24.0, 220.0, [zone])

    def test_berth_zone_beats_anchorage(self):
        anchorage = PortZone(
            zone_id="SANTOS-ANCH-1", port_id="SANTOS", zone="ANCHORAGE",
            polygon=((-24.2, -46.5), (-24.2, -46.1), (-23.8, -46.1), (-23.8, -46.5)),
            geofence_version="2026-08-26", source_id="validated_fixture",
        )
        berth = PortZone(
            zone_id="SANTOS-T1", port_id="SANTOS", terminal_id="T1", zone="BERTH",
            polygon=((-24.05, -46.35), (-24.05, -46.25), (-23.95, -46.25), (-23.95, -46.35)),
            geofence_version="2026-08-26", source_id="validated_fixture",
        )
        result = classify_position(-24.0, -46.30, [anchorage, berth], preferred_port_id="SANTOS")
        self.assertEqual(result["zone"], "BERTH")
        self.assertEqual(result["terminal_id"], "T1")
        self.assertEqual(result["geofence_version"], "2026-08-26")

    def test_lineup_portuguese_fields(self):
        call = normalize_lineup_row(
            {
                "Navio": "MV AGRO STAR",
                "IMO": "9876543",
                "ETA": "20/08/2026 12:00",
                "Produto": "Soja",
                "Toneladas": "60.000,00",
                "Situação": "Esperado",
                "DUV": "123456",
                "Terminal": "T1",
            },
            port_id="SANTOS",
            snapshot_id="2026-08-18T12:00Z",
            collected_at="2026-08-18T12:00:00Z",
            source_id="spa_lineup",
        )
        self.assertEqual(call.call_id, "spa_lineup:123456")
        self.assertEqual(call.imo, "9876543")
        self.assertEqual(call.planned_volume_t, 60000.0)
        self.assertEqual(call.lineup_status, "PROGRAMMED")
        self.assertEqual(call.terminal_id, "T1")

    def test_lineup_completed_remains_lineup_claim(self):
        call = normalize_lineup_row(
            {"Navio": "AGRO STAR", "ETA": "2026-08-20", "Status": "Concluído"},
            port_id="SANTOS",
            snapshot_id="snap",
            collected_at="2026-08-21T00:00:00Z",
            source_id="lineup",
        )
        self.assertEqual(call.lineup_status, "LINEUP_COMPLETED")


if __name__ == "__main__":
    unittest.main()
