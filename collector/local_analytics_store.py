from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

import duckdb

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"identificador SQL local inválido: {value!r}")
    return f'"{value}"'


class LocalAnalyticsStore:
    """DuckDB local analytical store for the ZERO_COST runtime.

    The database file is opened only for an operation and closed immediately.
    No daemon, cloud account, service credential, or paid runtime is required.
    """

    def __init__(self, db_path: str | Path, parquet_root: str | Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.parquet_root = Path(parquet_root) if parquet_root else self.db_path.parent / "parquet"
        self.parquet_root.mkdir(parents=True, exist_ok=True)

    def connect(self):
        return duckdb.connect(str(self.db_path))

    def ensure_table(self, schema: str, table: str, columns: dict[str, str]) -> None:
        schema_sql = _ident(schema)
        table_sql = _ident(table)
        if not columns:
            raise ValueError("columns cannot be empty")
        defs = ", ".join(f"{_ident(name)} {dtype}" for name, dtype in columns.items())
        create_schema_sql = f"CREATE SCHEMA IF NOT EXISTS {schema_sql}"  # nosec B608 - identifier validated by _ident
        create_table_sql = (  # nosec B608 - identifiers validated; column types are code-owned constants
            f"CREATE TABLE IF NOT EXISTS {schema_sql}.{table_sql} ({defs})"
        )
        with self.connect() as con:
            con.execute(create_schema_sql)
            con.execute(create_table_sql)

    def insert_rows(
        self,
        schema: str,
        table: str,
        rows: Iterable[dict[str, Any]],
        *,
        columns: list[str],
    ) -> int:
        data = list(rows)
        if not data:
            return 0
        if not columns:
            raise ValueError("columns cannot be empty")
        schema_sql = _ident(schema)
        table_sql = _ident(table)
        column_sql = ", ".join(_ident(name) for name in columns)
        placeholders = ", ".join("?" for _ in columns)
        values = [[row.get(name) for name in columns] for row in data]
        insert_sql = (  # nosec B608 - identifiers validated by _ident; all row values are placeholders
            f"INSERT INTO {schema_sql}.{table_sql} ({column_sql}) VALUES ({placeholders})"
        )
        with self.connect() as con:
            con.executemany(insert_sql, values)
        return len(data)

    def query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        with self.connect() as con:
            cursor = con.execute(sql, params or [])
            names = [item[0] for item in cursor.description or []]
            return [dict(zip(names, row)) for row in cursor.fetchall()]

    def scalar(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    def export_table_parquet(self, schema: str, table: str) -> Path:
        schema_sql = _ident(schema)
        table_sql = _ident(table)
        out_dir = self.parquet_root / schema
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{table}.parquet"
        safe_target = str(target).replace("'", "''")
        copy_sql = (  # nosec B608 - identifiers validated; target is a locally constructed path with quotes escaped
            f"COPY (SELECT * FROM {schema_sql}.{table_sql}) "
            f"TO '{safe_target}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        with self.connect() as con:
            con.execute(copy_sql)
        return target

    def table_exists(self, schema: str, table: str) -> bool:
        value = self.scalar(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema=? AND table_name=?
            """,
            [schema, table],
        )
        return bool(value)

    def manifest(self) -> dict[str, Any]:
        rows = self.query(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'main')
            ORDER BY table_schema, table_name
            """
        )
        return {
            "backend": "duckdb",
            "db_path": str(self.db_path),
            "paid_runtime_required": False,
            "cloud_credentials_required": False,
            "tables": rows,
        }

    def write_manifest(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target
