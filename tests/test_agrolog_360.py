from __future__ import annotations

import unittest
from datetime import date

from models.agrolog_360 import (
    ClimateDay,
    competence_from_reference,
    export_parity,
    fertilizer_exchange_ratio,
    normalize_freight,
    port_pressure,
    rolling_precipitation,
    storage_balance,
)


class AgroLog360ModelsTests(unittest.TestCase):
    def test_rolling_precipitation_respects_trailing_windows(self) -> None:
        rows = [
            ClimateDay(date(2026, 9, 1), 10),
            ClimateDay(date(2026, 9, 5), 5),
            ClimateDay(date(2026, 9, 10), 20),
        ]
        result = rolling_precipitation(rows, windows=(7, 15), as_of=date(2026, 9, 10))
        self.assertEqual(result[7], 25.0)
        self.assertEqual(result[15], 35.0)

    def test_missing_precipitation_is_not_silently_zero(self) -> None:
        result = rolling_precipitation(
            [ClimateDay(date(2026, 9, 10), None)],
            windows=(7,),
        )
        self.assertIsNone(result[7])

    def test_storage_balance_distinguishes_deficit_and_surplus(self) -> None:
        deficit = storage_balance(production_t=120, static_capacity_t=100)
        surplus = storage_balance(production_t=60, static_capacity_t=100)
        self.assertEqual(deficit.status, "DEFICIT")
        self.assertEqual(deficit.capacity_gap_t, -20.0)
        self.assertEqual(surplus.status, "SURPLUS")

    def test_freight_normalization_handles_per_t_and_per_trip(self) -> None:
        per_t = normalize_freight(value_brl=180, unit="R$/t", distance_km=900, payload_t=37)
        self.assertAlmostEqual(per_t.brl_per_t_km or 0, 0.2)
        self.assertEqual(per_t.announced_brl_per_trip, 6660.0)

        trip = normalize_freight(value_brl=6660, unit="R$/viagem", distance_km=900, payload_t=37)
        self.assertAlmostEqual(trip.announced_brl_per_t, 180.0)

    def test_freight_rejects_ambiguous_unit(self) -> None:
        with self.assertRaises(ValueError):
            normalize_freight(value_brl=100, unit="por carga")

    def test_export_parity_keeps_components_auditable(self) -> None:
        result = export_parity(
            port_fob_usd_per_t=450,
            fx_brl_per_usd=5,
            inland_freight_brl_per_t=300,
            port_cost_brl_per_t=50,
            taxes_and_fees_brl_per_t=25,
        )
        self.assertEqual(result.gross_port_brl_per_t, 2250.0)
        self.assertEqual(result.farmgate_parity_brl_per_t, 1875.0)

    def test_fertilizer_exchange_ratio(self) -> None:
        self.assertEqual(
            fertilizer_exchange_ratio(fertilizer_brl_per_t=2500, grain_brl_per_t=1250),
            2.0,
        )

    def test_port_pressure_is_bounded_and_descriptive(self) -> None:
        result = port_pressure(
            anchorage_vessels=8,
            berth_vessels=2,
            programmed_mass_t=700_000,
            observed_throughput_t_day=100_000,
        )
        self.assertEqual(result.queue_to_berth_ratio, 4.0)
        self.assertEqual(result.programmed_days_of_throughput, 7.0)
        self.assertEqual(result.pressure_index, 100.0)

    def test_competence(self) -> None:
        self.assertEqual(competence_from_reference("2026-09-29"), "2026-09")


if __name__ == "__main__":
    unittest.main()
