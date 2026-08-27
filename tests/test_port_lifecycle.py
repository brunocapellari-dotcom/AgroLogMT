from __future__ import annotations

import unittest
from datetime import datetime, timezone

from collector.port_lifecycle import PortCallObservation, multiport_readiness, promote_state

NOW = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


def obs(system: str, *, state: str = "PROGRAMADO", hours_old: int = 1, berth: str | None = None, unberth: str | None = None, realized: float | None = None) -> PortCallObservation:
    observed = datetime(2026, 8, 25, 13 - hours_old, 0, tzinfo=timezone.utc)
    return PortCallObservation(
        port_system=system,
        source_url="https://official.example/source",
        observed_at=observed.isoformat(),
        data_referencia="2026-08-25",
        ship_name="TEST SHIP",
        imo="1234567",
        duv=f"DUV-{system}",
        state=state,
        quantity_programmed_t=50000.0,
        quantity_realized_t=realized,
        berth_at=berth,
        unberth_at=unberth,
    )


class PortLifecycleTests(unittest.TestCase):
    def test_santos_alone_is_partial(self) -> None:
        result = multiport_readiness([obs("SANTOS")], now=NOW)
        self.assertEqual(result["status"], "PARTIAL_MULTI_PORT")
        self.assertIn("PARANAGUA", result["missing_or_stale_systems"])
        self.assertIn("BARCARENA_VILA_DO_CONDE", result["missing_or_stale_systems"])
        self.assertIn("SANTAREM", result["missing_or_stale_systems"])
        self.assertIn("ITAQUI", result["missing_or_stale_systems"])

    def test_five_pilot_ports_are_required(self) -> None:
        rows = [
            obs("SANTOS"),
            obs("PARANAGUA"),
            obs("BARCARENA_VILA_DO_CONDE"),
            obs("SANTAREM"),
            obs("ITAQUI"),
        ]
        result = multiport_readiness(rows, now=NOW)
        self.assertEqual(result["status"], "MULTIPORT_VALIDATED")
        self.assertEqual(len(result["covered_systems"]), 5)

    def test_legacy_combined_ids_do_not_fake_v1_coverage(self) -> None:
        rows = [
            obs("SANTOS"),
            obs("PARANAGUA_ANTONINA"),
            obs("ARCO_NORTE_CDP"),
            obs("ITAQUI"),
        ]
        result = multiport_readiness(rows, now=NOW)
        self.assertEqual(result["status"], "PARTIAL_MULTI_PORT")
        self.assertIn("PARANAGUA", result["missing_or_stale_systems"])
        self.assertIn("BARCARENA_VILA_DO_CONDE", result["missing_or_stale_systems"])
        self.assertIn("SANTAREM", result["missing_or_stale_systems"])
        self.assertEqual(
            result["legacy_observations"],
            {"ARCO_NORTE_CDP": 1, "PARANAGUA_ANTONINA": 1},
        )

    def test_programmed_quantity_cannot_be_realized_before_completion(self) -> None:
        with self.assertRaises(ValueError):
            multiport_readiness([obs("SANTOS", state="ATRACADO", berth="2026-08-25T12:00:00+00:00", realized=50000)], now=NOW)

    def test_berthing_requires_explicit_berth_timestamp(self) -> None:
        previous = obs("SANTOS")
        current = obs("SANTOS", state="ATRACADO")
        with self.assertRaises(ValueError):
            promote_state(previous, current)

    def test_explicit_programmed_to_berthed_transition_passes(self) -> None:
        previous = obs("SANTOS")
        current = obs("SANTOS", state="ATRACADO", berth="2026-08-25T12:00:00+00:00")
        self.assertEqual(promote_state(previous, current).state, "ATRACADO")

    def test_completed_call_can_keep_realized_tonnage_unknown(self) -> None:
        previous = obs("SANTOS", state="ATRACADO", berth="2026-08-25T12:00:00+00:00")
        current = obs("SANTOS", state="CONCLUIDO", berth="2026-08-25T12:00:00+00:00", unberth="2026-08-25T15:00:00+00:00")
        result = promote_state(previous, current)
        self.assertEqual(result.state, "CONCLUIDO")
        self.assertIsNone(result.quantity_realized_t)
        self.assertEqual(result.quantity_programmed_t, 50000.0)

    def test_state_regression_is_blocked(self) -> None:
        previous = obs("SANTOS", state="ATRACADO", berth="2026-08-25T12:00:00+00:00")
        current = obs("SANTOS", state="PROGRAMADO")
        with self.assertRaises(ValueError):
            promote_state(previous, current)


if __name__ == "__main__":
    unittest.main()
