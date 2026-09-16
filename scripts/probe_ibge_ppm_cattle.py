from __future__ import annotations

import argparse
import json

from collector.ibge_ppm import build_canonical_rows, fetch_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe live IBGE SIDRA PPM cattle herd for Mato Grosso municipalities.")
    parser.add_argument("--period", default="2024", help="PPM year or 'all'.")
    parser.add_argument("--min-municipalities", type=int, default=100)
    parser.add_argument("--min-year", type=int)
    parser.add_argument("--max-year", type=int)
    args = parser.parse_args()

    payload, source_url = fetch_payload(period=args.period)
    rows, stats = build_canonical_rows(payload, source_url=source_url)

    if stats["municipalities"] < args.min_municipalities:
        raise RuntimeError(
            f"PPM live probe returned only {stats['municipalities']} municipalities; "
            f"expected at least {args.min_municipalities}"
        )
    if str(args.period) != "all":
        expected_year = int(args.period)
        observed_years = {int(row["year"]) for row in rows}
        if observed_years != {expected_year}:
            raise RuntimeError(f"PPM live probe year mismatch: {sorted(observed_years)}")
    if args.min_year is not None and int(stats["year_min"]) > args.min_year:
        raise RuntimeError(
            f"PPM live probe starts at {stats['year_min']}; expected coverage from {args.min_year} or earlier"
        )
    if args.max_year is not None and int(stats["year_max"]) < args.max_year:
        raise RuntimeError(
            f"PPM live probe ends at {stats['year_max']}; expected coverage through {args.max_year} or later"
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "source_url": source_url,
                "stats": stats,
                "sample": rows[:3],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
