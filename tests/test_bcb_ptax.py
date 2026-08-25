from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from collector.bcb_ptax import PtaxQuote, classify_daily_state, dollar_day_url, parse_quotes

BRASILIA = ZoneInfo("America/Sao_Paulo")


def q(day: date, hour: int, minute: int = 0) -> PtaxQuote:
    return PtaxQuote(day.isoformat(), datetime(day.year, day.month, day.day, hour, minute, tzinfo=BRASILIA).isoformat(), 5.1, 5.2)


class PtaxTests(unittest.TestCase):
    def test_official_odata_url_is_date_scoped(self) -> None:
        url = dollar_day_url(date(2026, 8, 25))
        self.assertIn("olinda.bcb.gov.br", url)
        self.assertIn("08-25-2026", url)
        self.assertIn("CotacaoDolarDia", url)

    def test_before_final_window_missing_is_not_lag(self) -> None:
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=[], now=datetime(2026, 8, 25, 10, 15, tzinfo=BRASILIA))
        self.assertEqual(state, "NOT_YET_PUBLISHED")

    def test_intraday_is_not_closing(self) -> None:
        rows = [q(date(2026, 8, 25), 10), q(date(2026, 8, 25), 11)]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 12, 30, tzinfo=BRASILIA))
        self.assertEqual(state, "INTRADAY_ONLY")

    def test_after_window_incomplete_is_source_lag(self) -> None:
        rows = [q(date(2026, 8, 25), 10), q(date(2026, 8, 25), 11), q(date(2026, 8, 25), 12)]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 14, 0, tzinfo=BRASILIA))
        self.assertEqual(state, "SOURCE_LAG")

    def test_normal_four_consultations_after_window_is_closing(self) -> None:
        rows = [q(date(2026, 8, 25), h) for h in (10, 11, 12, 13)]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 14, 0, tzinfo=BRASILIA))
        self.assertEqual(state, "CLOSING_PUBLISHED")

    def test_previous_day_never_substitutes_current(self) -> None:
        rows = [q(date(2026, 8, 24), h) for h in (10, 11, 12, 13)]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 10, 15, tzinfo=BRASILIA))
        self.assertEqual(state, "NOT_YET_PUBLISHED")

    def test_parse_rejects_wrong_reference_day(self) -> None:
        payload = {"value": [{"cotacaoCompra": 5.1, "cotacaoVenda": 5.2, "dataHoraCotacao": "2026-08-24 13:00:00.000"}]}
        self.assertEqual(parse_quotes(payload, reference_date=date(2026, 8, 25)), [])


if __name__ == "__main__":
    unittest.main()
