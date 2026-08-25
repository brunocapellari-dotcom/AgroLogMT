#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from collector.bcb_ptax import BRASILIA, classify_daily_state, closing_quote, fetch_dollar_day


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe read-only da PTAX USD oficial do BCB")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD; padrão: hoje em Brasília")
    args = ap.parse_args()
    now = datetime.now(BRASILIA)
    reference = date.fromisoformat(args.date) if args.date else now.date()
    quotes, url = fetch_dollar_day(reference)
    state = classify_daily_state(reference_date=reference, quotes=quotes, now=now)
    closing = closing_quote(quotes, reference_date=reference)
    payload = {
        "reference_date": reference.isoformat(),
        "collected_at": now.isoformat(),
        "source_url": url,
        "state": state,
        "observations": len(quotes),
        "closing": closing.to_dict() if closing else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if state in {"CLOSING_PUBLISHED", "NOT_YET_PUBLISHED", "INTRADAY_ONLY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
