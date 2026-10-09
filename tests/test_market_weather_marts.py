from __future__ import annotations

import unittest

from models.agrolog_360_marts import (
    freight_lanes_sql,
    imea_market_indicators_sql,
    weather_consensus_sql,
    weather_run_summary_sql,
)


class IntelligenceMarketWeatherMartTests(unittest.TestCase):
    def test_freight_mart_exposes_trip_distance_and_tku_when_available(self) -> None:
        sql = freight_lanes_sql("agrolog-prod").sql
        for token in ("distance_km_p50", "payload_t_p50", "announced_brl_per_trip_p50", "freight_brl_per_km_p50", "tku_estimated_p50"):
            self.assertIn(token, sql)

    def test_imea_market_history_has_previous_7d_30d_and_percentile(self) -> None:
        sql = imea_market_indicators_sql("agrolog-prod").sql
        for token in ("previous_value", "avg_7d", "avg_30d", "historical_percentile"):
            self.assertIn(token, sql)

    def test_weather_consensus_is_based_on_latest_run_per_model(self) -> None:
        run_sql = weather_run_summary_sql("agrolog-prod").sql
        consensus_sql = weather_consensus_sql("agrolog-prod").sql
        self.assertIn("run_delta_value", run_sql)
        self.assertIn("ROW_NUMBER()", consensus_sql)
        self.assertIn("model_iqr", consensus_sql)
        self.assertIn("models_revised_up", consensus_sql)
        self.assertNotIn("AVG(run_median_value)", consensus_sql)


if __name__ == "__main__":
    unittest.main()
