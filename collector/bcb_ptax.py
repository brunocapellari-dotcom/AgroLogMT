from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
BRASILIA = ZoneInfo("America/Sao_Paulo")
NORMAL_FINAL_WINDOW_END = time(13, 10)
NORMAL_CONSULTATIONS = 4
# Comunicado BCB 44.603/2026: horários excepcionais da PTAX em 2026.
SPECIAL_SCHEDULE_2026: dict[date, tuple[time, int]] = {
    date(2026, 2, 18): (time(15, 40), 2),
    date(2026, 12, 24): (time(11, 10), 2),
    # 31/12 é excepcional: o fechamento repete USD/BRL de 30/12. Deve ser tratado
    # por boletim explícito, nunca inferido pela contagem de consultas do próprio dia.
    date(2026, 12, 31): (time(10, 10), 0),
}


@dataclass(frozen=True)
class PtaxQuote:
    reference_date: str
    quote_time: str
    buy: float
    sell: float
    bulletin_type: str | None = None
    evidence_class: str = "observado"
    evidence_subtype: str = "bcb_ptax_official"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _odata_date(value: date) -> str:
    return value.strftime("%m-%d-%Y")


def dollar_day_url(value: date) -> str:
    literal = quote(f"'{_odata_date(value)}'", safe="'()")
    return f"{BASE_URL}/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao={literal}&$format=json"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BRASILIA)
    return parsed.astimezone(BRASILIA)


def parse_quotes(payload: Any, *, reference_date: date) -> list[PtaxQuote]:
    values = payload.get("value", []) if isinstance(payload, dict) else []
    out: list[PtaxQuote] = []
    for row in values:
        if not isinstance(row, dict):
            continue
        ts = _parse_datetime(row.get("dataHoraCotacao"))
        buy = row.get("cotacaoCompra")
        sell = row.get("cotacaoVenda")
        if ts is None or buy is None or sell is None or ts.date() != reference_date:
            continue
        out.append(
            PtaxQuote(
                reference_date=reference_date.isoformat(),
                quote_time=ts.isoformat(),
                buy=float(buy),
                sell=float(sell),
                bulletin_type=(str(row.get("tipoBoletim")) if row.get("tipoBoletim") else None),
            )
        )
    out.sort(key=lambda item: item.quote_time)
    return out


def expected_schedule(value: date) -> tuple[time, int]:
    return SPECIAL_SCHEDULE_2026.get(value, (NORMAL_FINAL_WINDOW_END, NORMAL_CONSULTATIONS))


def classify_daily_state(*, reference_date: date, quotes: list[PtaxQuote], now: datetime) -> str:
    """Fail-closed temporal classifier for one PTAX reference day.

    Previous-day values are never promoted to the current day. On normal days the
    closing is accepted only after the official final consultation window and after
    the expected number of same-day consultation observations is present. Explicit
    closing bulletin metadata, when supplied by an official endpoint, takes precedence.
    """
    local_now = now.astimezone(BRASILIA)
    if reference_date > local_now.date():
        return "FUTURE_DATE"
    same_day = [q for q in quotes if q.reference_date == reference_date.isoformat()]
    final_window_end, expected_count = expected_schedule(reference_date)
    expected_end = datetime.combine(reference_date, final_window_end, tzinfo=BRASILIA)

    final_types = {"fechamento", "closing", "final"}
    if any((q.bulletin_type or "").strip().lower() in final_types for q in same_day):
        return "CLOSING_PUBLISHED"

    if local_now < expected_end:
        return "INTRADAY_ONLY" if same_day else "NOT_YET_PUBLISHED"

    if expected_count == 0:
        return "NEEDS_EXPLICIT_CLOSING_BULLETIN"
    if len(same_day) >= expected_count:
        return "CLOSING_PUBLISHED"
    return "SOURCE_LAG"


def fetch_dollar_day(value: date, *, timeout: int = 30) -> tuple[list[PtaxQuote], str]:
    url = dollar_day_url(value)
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "AgroLogMT/0.1 (+BCB PTAX)"})
    with urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_quotes(payload, reference_date=value), url
