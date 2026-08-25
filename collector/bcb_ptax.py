from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata"
BRASILIA = ZoneInfo("America/Sao_Paulo")
NORMAL_FINAL_WINDOW_END = time(13, 10)
# Comunicado BCB 44.603/2026: horários excepcionais do fechamento PTAX em 2026.
SPECIAL_FINAL_WINDOW_END_2026: dict[date, time] = {
    date(2026, 2, 18): time(15, 40),
    date(2026, 12, 24): time(11, 10),
    date(2026, 12, 31): time(10, 10),
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
    return (
        f"{BASE_URL}/CotacaoDolarDia(dataCotacao=@dataCotacao)"
        f"?@dataCotacao={literal}&$format=json"
    )


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
        if ts is None or buy is None or sell is None:
            continue
        if ts.date() != reference_date:
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


def expected_final_window_end(value: date) -> time:
    return SPECIAL_FINAL_WINDOW_END_2026.get(value, NORMAL_FINAL_WINDOW_END)


def classify_daily_state(*, reference_date: date, quotes: list[PtaxQuote], now: datetime) -> str:
    """Fail-closed temporal classifier for a PTAX day.

    It never substitutes a previous business day. Before the expected final consultation
    window ends, lack of a final quote is NOT_YET_PUBLISHED. Afterwards it becomes
    SOURCE_LAG unless a same-day closing/final observation is present.
    """
    local_now = now.astimezone(BRASILIA)
    if reference_date > local_now.date():
        return "FUTURE_DATE"
    same_day = [q for q in quotes if q.reference_date == reference_date.isoformat()]
    expected_end = datetime.combine(reference_date, expected_final_window_end(reference_date), tzinfo=BRASILIA)
    if not same_day:
        return "NOT_YET_PUBLISHED" if local_now < expected_end else "SOURCE_LAG"

    final_types = {"fechamento", "closing", "final"}
    if any((q.bulletin_type or "").strip().lower() in final_types for q in same_day):
        return "CLOSING_PUBLISHED"

    latest = max(_parse_datetime(q.quote_time) for q in same_day)
    if latest is None:
        return "DATA_QUALITY_BLOCK"
    if latest >= expected_end.replace(minute=0 if expected_end.hour == 10 and reference_date == date(2026, 12, 31) else expected_end.minute):
        # CotacaoDolarDia commonly omits tipoBoletim. A same-day observation at/after
        # the final window is acceptable as the final observation only after that window.
        return "CLOSING_PUBLISHED" if local_now >= expected_end else "INTRADAY_ONLY"
    return "INTRADAY_ONLY" if local_now < expected_end else "SOURCE_LAG"


def fetch_dollar_day(value: date, *, timeout: int = 30) -> tuple[list[PtaxQuote], str]:
    url = dollar_day_url(value)
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "AgroLogMT/0.1 (+BCB PTAX)"})
    with urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_quotes(payload, reference_date=value), url
