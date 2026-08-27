import unittest
from datetime import datetime, timezone

from models.shipping_reconciliation import AISObservation, LineupCall, reconcile_call

UTC = timezone.utc


def ts(day: int, hour: int = 0):
    return datetime(2026, 8, day, hour, tzinfo=UTC)


class ShippingScopeTests(unittest.TestCase):
    def test_other_port_does_not_contaminate_current_call(self):
        call = LineupCall(
            call_id="CALL-SANTOS",
            port_id="SANTOS",
            terminal_id="T1",
            vessel_name="AGRO STAR",
            imo="9876543",
            mmsi="710123456",
            eta=ts(20, 12),
            collected_at=ts(18),
        )
        observations = [
            AISObservation(ts(20, 10), imo="9876543", mmsi="710123456", vessel_name="AGRO STAR", port_id="SANTOS", zone="ANCHORAGE"),
            AISObservation(ts(20, 16), imo="9876543", mmsi="710123456", vessel_name="AGRO STAR", port_id="SANTOS", terminal_id="T1", zone="BERTH"),
            AISObservation(ts(23, 8), imo="9876543", mmsi="710123456", vessel_name="AGRO STAR", port_id="PARANAGUA", zone="ANCHORAGE"),
        ]
        result = reconcile_call(call, observations)
        self.assertEqual(result.state, "BERTHED")
        self.assertEqual(result.metadata["ais_observations_scoped"], 2)
        self.assertNotIn("ais_port_divergence", result.flags)

    def test_paranagua_legacy_alias_is_accepted_only_for_paranagua(self):
        call = LineupCall(
            call_id="CALL-PARANAGUA",
            port_id="PARANAGUA",
            vessel_name="AGRO STAR",
            imo="9876543",
            eta=ts(20, 12),
            collected_at=ts(18),
        )
        observations = [
            AISObservation(ts(20, 10), imo="9876543", vessel_name="AGRO STAR", port_id="PARANAGUA_ANTONINA", zone="ANCHORAGE"),
        ]
        result = reconcile_call(call, observations)
        self.assertEqual(result.state, "ARRIVED_WAITING")
        self.assertEqual(result.metadata["ais_observations_scoped"], 1)


if __name__ == "__main__":
    unittest.main()
