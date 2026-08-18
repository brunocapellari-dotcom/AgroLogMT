from __future__ import annotations

from datetime import date, timedelta


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def expected_references(start: str, end: str, frequency: str) -> list[str]:
    frequency = frequency.lower().strip()
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if end_date < start_date:
        raise ValueError("end anterior a start")

    if frequency in {"daily", "diaria"}:
        out = []
        cursor = start_date
        while cursor <= end_date:
            out.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return out

    if frequency in {"business_daily", "daily_business", "diaria_util"}:
        out = []
        cursor = start_date
        while cursor <= end_date:
            if cursor.weekday() < 5:
                out.append(cursor.isoformat())
            cursor += timedelta(days=1)
        return out

    if frequency in {"weekly", "semanal"}:
        out = []
        cursor = start_date
        while cursor <= end_date:
            out.append(cursor.isoformat())
            cursor += timedelta(days=7)
        return out

    if frequency in {"monthly", "mensal"}:
        out = []
        year, month = start_date.year, start_date.month
        while (year, month) <= (end_date.year, end_date.month):
            out.append(f"{year:04d}-{month:02d}")
            month += 1
            if month == 13:
                year += 1
                month = 1
        return out

    raise ValueError(f"Frequencia nao suportada: {frequency}")


def detect_gaps(observed: list[str], start: str, end: str, frequency: str) -> list[str]:
    expected = expected_references(start, end, frequency)
    observed_set = {str(value) for value in observed}
    return [ref for ref in expected if ref not in observed_set]
