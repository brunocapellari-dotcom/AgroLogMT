from __future__ import annotations

import unittest

from gateway.maritime_queries import (
    build_lineup_reconciliation_sql,
    build_live_vessels_sql,
    build_port_summary_sql,
    build_vessel_replay_sql,
    normalize_mmsi,
    normalize_port_id,
)


class MaritimeQueryTests(unittest.TestCase):
    def test_port_id_normalization(self) -> None:
        self.assertEqual(normalize_port_id(" santos "), "SANTOS")
        self.assertEqual(normalize_port_id("barcarena_vila_do_conde"), "BARCARENA_VILA_DO_CONDE")
        self.assertIsNone(normalize_port_id(None))
        with self.assertRaises(ValueError):
            normalize_port_id("SANTOS;DROP TABLE")

    def test_mmsi_normalization_requires_real_nine_digit_shape(self) -> None:
        self.assertEqual(normalize_mmsi("710123456"), "710123456")
        for invalid in ("710-123-456", "123456", "000000000", "7101234567"):
            with self.assertRaises(ValueError):
                normalize_mmsi(invalid)

    def test_live_query_uses_parameters_latest_and_quality_gate(self) -> None:
        sql = build_live_vessels_sql("project-1", "agrolog_models")
        self.assertIn("shipping_ais_positions", sql)
        self.assertIn("ROW_NUMBER() OVER", sql)
        self.assertIn("@hours", sql)
        self.assertIn("@port_id", sql)
        self.assertIn("@limit", sql)
        self.assertIn("quality_status = 'CONFIRMED_SEQUENCE'", sql)
        self.assertIn("corroborated IS TRUE", sql)
        self.assertIn("spoofing_suspected, FALSE", sql)
        self.assertNotIn("SANTOS;", sql)

    def test_paranagua_filter_keeps_only_safe_legacy_alias(self) -> None:
        sql = build_live_vessels_sql("project-1", "agrolog_models")
        self.assertIn("PARANAGUA_ANTONINA", sql)
        self.assertNotIn("ARCO_NORTE_CDP", sql)

    def test_replay_is_ordered_parameterized_and_keeps_quality_for_forensics(self) -> None:
        sql = build_vessel_replay_sql("project-1", "agrolog_models")
        self.assertIn("mmsi = @mmsi", sql)
        self.assertIn("COALESCE(@end_at, CURRENT_TIMESTAMP())", sql)
        self.assertIn("ORDER BY observed_at ASC", sql)
        self.assertIn("quality_status", sql)
        self.assertIn("spoofing_suspected", sql)
        self.assertNotIn("quality_status = 'CONFIRMED_SEQUENCE'", sql)

    def test_lineup_keeps_programmed_separate_from_reconciled(self) -> None:
        sql = build_lineup_reconciliation_sql("project-1", "agrolog_models")
        self.assertIn("shipping_lineup_calls", sql)
        self.assertIn("shipping_reconciliation", sql)
        self.assertIn("planned_volume_t", sql)
        self.assertIn("reconciled_state", sql)
        self.assertIn("evidence_class", sql)
        self.assertIn("LEFT JOIN", sql)

    def test_summary_uses_only_trusted_ais_and_does_not_claim_unavailable_dwt(self) -> None:
        sql = build_port_summary_sql("project-1", "agrolog_models")
        self.assertIn("vessels_waiting", sql)
        self.assertIn("waiting_p90_hours", sql)
        self.assertIn("eta_mae_hours", sql)
        self.assertIn("quality_status = 'CONFIRMED_SEQUENCE'", sql)
        self.assertIn("corroborated IS TRUE", sql)
        self.assertNotIn("DWT", sql.upper())

    def test_identifier_injection_is_blocked(self) -> None:
        with self.assertRaises(ValueError):
            build_live_vessels_sql("project`;DROP", "agrolog_models")


if __name__ == "__main__":
    unittest.main()
