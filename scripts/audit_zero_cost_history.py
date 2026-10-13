"""Evidence/temporal quality audit for the ZERO_COST DuckDB historical store.

This does not create records, update vintages, infer prices or mark live sources
as healthy. It is a read-only, bounded inspection of materialized history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from collector.local_analytics_store import _ident


def audit_history(db_path: str | Path) -> dict[str, Any]:
    database = Path(db_path).resolve(strict=True)
    if not database.is_file():
        raise ValueError("historical store must be a DuckDB file")
    tables: list[dict[str, Any]] = []
    critical_count = 0
    # Read-only means the audit never changes the source, even on failure.
    with duckdb.connect(str(database), read_only=True) as con:
        catalog = con.execute(
            """
            SELECT table_schema, table_name FROM information_schema.tables
            WHERE table_type='BASE TABLE'
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
            """
        ).fetchall()
        for schema, table in catalog:
            qualified = f"{_ident(schema)}.{_ident(table)}"
            columns = {
                row[0] for row in con.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema=? AND table_name=?
                    """,
                    [schema, table],
                ).fetchall()
            }
            count = int(con.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()[0])
            checks: list[dict[str, object]] = []

            def check(name: str, where: str) -> None:
                nonlocal critical_count
                bad = int(con.execute(f"SELECT COUNT(*) FROM {qualified} WHERE {where}").fetchone()[0])
                checks.append({"code": name, "violations": bad, "severity": "CRITICAL" if bad else "PASS"})
                if bad:
                    critical_count += 1

            for col in ("data_coleta", "data_referencia", "evidence_class"):
                if col in columns:
                    check(f"{col}_present", f"{_ident(col)} IS NULL")
            for col in ("snapshot_sha256", "source_hash"):
                if col in columns:
                    check(f"{col}_present", f"{_ident(col)} IS NULL OR TRIM(CAST({_ident(col)} AS VARCHAR)) = ''")
            if {"availability_verified", "data_disponibilidade"} <= columns:
                check(
                    "verified_availability_requires_timestamp",
                    '"availability_verified" = TRUE AND "data_disponibilidade" IS NULL',
                )
            if {"data_publicacao", "data_coleta"} <= columns:
                check(
                    "publication_not_after_collection",
                    '"data_publicacao" > "data_coleta"',
                )
            if {"record_id", "snapshot_id"} <= columns:
                n = int(con.execute(
                    f"""SELECT COUNT(*) FROM (
                        SELECT record_id, snapshot_id FROM {qualified}
                        GROUP BY record_id, snapshot_id HAVING COUNT(*) > 1
                    )"""
                ).fetchone()[0])
                checks.append({
                    "code": "duplicate_record_within_snapshot",
                    "violations": n,
                    "severity": "CRITICAL" if n else "PASS",
                })
                critical_count += int(n > 0)
            coverage = {}
            for col in ("data_referencia", "data_publicacao", "data_coleta"):
                if col in columns and count:
                    low, high = con.execute(
                        f"SELECT MIN({_ident(col)}), MAX({_ident(col)}) FROM {qualified}"
                    ).fetchone()
                    coverage[col] = {
                        "min": low.isoformat() if low is not None else None,
                        "max": high.isoformat() if high is not None else None,
                    }
            tables.append({
                "schema": schema,
                "table": table,
                "records": count,
                "coverage": coverage,
                "checks": checks,
                "note": "Coverage is stored history, not confirmation of source completeness.",
            })
    return {
        "status": "BLOCKED" if critical_count or not tables else "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
        "table_count": len(tables),
        "critical_check_groups": critical_count,
        "tables": tables,
        "claims_live_source_freshness": False,
        "claims_point_in_time_history_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only historical quality audit (DuckDB)")
    parser.add_argument("--db", default=".agrolog-zero-cost/analytics/agrolog.duckdb")
    parser.add_argument("--out", default="outputs/zero-cost-historical-quality.json")
    args = parser.parse_args()
    report = audit_history(args.db)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "table_count": report["table_count"], "critical_check_groups": report["critical_check_groups"], "report": str(out)}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
