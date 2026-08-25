from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from collector.bcb_ptax import PtaxQuote, classify_daily_state, closing_quote, dollar_day_url, parse_quotes

BRASILIA = ZoneInfo("America/Sao_Paulo")


def q(day: date, hour: int, minute: int = 0, bulletin_type: str | None = None) -> PtaxQuote:
    return PtaxQuote(day.isoformat(), datetime(day.year, day.month, day.day, hour, minute, tzinfo=BRASILIA).isoformat(), 5.1, 5.2, bulletin_type)


class PtaxTests(unittest.TestCase):
    def test_official_odata_url_is_date_and_currency_scoped(self) -> None:
        url = dollar_day_url(date(2026, 8, 25))
        self.assertIn("olinda.bcb.gov.br", url)
        self.assertIn("08-25-2026", url)
        self.assertIn("CotacaoMoedaDia", url)
        self.assertIn("USD", url)

    def test_before_final_window_missing_is_not_lag(self) -> None:
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=[], now=datetime(2026, 8, 25, 10, 15, tzinfo=BRASILIA))
        self.assertEqual(state, "NOT_YET_PUBLISHED")

    def test_intraday_is_not_closing(self) -> None:
        rows = [q(date(2026, 8, 25), 10, bulletin_type="Abertura"), q(date(2026, 8, 25), 11, bulletin_type="Intermediário")]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 12, 30, tzinfo=BRASILIA))
        self.assertEqual(state, "INTRADAY_ONLY")

    def test_after_window_without_explicit_closing_is_source_lag(self) -> None:
        rows = [q(date(2026, 8, 25), h, bulletin_type="Intermediário") for h in (10, 11, 12, 13)]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 14, 0, tzinfo=BRASILIA))
        self.assertEqual(state, "SOURCE_LAG")

    def test_explicit_closing_is_published(self) -> None:
        rows = [q(date(2026, 8, 25), 13, 5, bulletin_type="Fechamento")]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 13, 8, tzinfo=BRASILIA))
        self.assertEqual(state, "CLOSING_PUBLISHED")
        self.assertIsNotNone(closing_quote(rows, reference_date=date(2026, 8, 25)))

    def test_previous_day_never_substitutes_current(self) -> None:
        rows = [q(date(2026, 8, 24), 13, bulletin_type="Fechamento")]
        state = classify_daily_state(reference_date=date(2026, 8, 25), quotes=rows, now=datetime(2026, 8, 25, 10, 15, tzinfo=BRASILIA))
        self.assertEqual(state, "NOT_YET_PUBLISHED")

    def test_parse_keeps_bulletin_type_and_rejects_wrong_day(self) -> None:
        payload = {"value": [
            {"cotacaoCompra": 5.1, "cotacaoVenda": 5.2, "dataHoraCotacao": "2026-08-25 13:05:00.000", "tipoBoletim": "Fechamento"},
            {"cotacaoCompra": 5.0, "cotacaoVenda": 5.1, "dataHoraCotacao": "2026-08-24 13:00:00.000", "tipoBoletim": "Fechamento"},
        ]}
        rows = parse_quotes(payload, reference_date=date(2026, 8, 25))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].bulletin_type, "Fechamento")


if __name__ == "__main__":
    unittest.main()
