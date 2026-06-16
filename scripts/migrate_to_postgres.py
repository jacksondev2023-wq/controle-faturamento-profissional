#!/usr/bin/env python3
"""
migrate_to_postgres.py
======================
One-time migration script to move data from a local SQLite database
to a remote PostgreSQL instance (e.g., Supabase).

Usage examples
--------------
# Migrate all tables (SQLite at default path)
python scripts/migrate_to_postgres.py \
    --pg-url "postgresql://postgres:PASS@db.XXXXX.supabase.co:6543/postgres"

# Migrate specific tables from a custom SQLite path
python scripts/migrate_to_postgres.py \
    --db "data/app.db" \
    --pg-url "postgresql://postgres:PASS@db.XXXXX.supabase.co:6543/postgres" \
    --tables "faturamento,contabilidade"

Requirements
------------
- pandas
- sqlalchemy
- psycopg2-binary  (PostgreSQL driver)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# ---------------------------------------------------------------------------
# All known tables in the SQLite database (migration order)
# ---------------------------------------------------------------------------
ALL_TABLES: list[str] = [
    "base_dinamica",
    "faturamento",
    "contabilidade",
    "de_para_unidades",
    "de_para_operadoras",
    "comentarios_manuais",
    "importacoes",
    "exportacoes",
    "inconsistencias_manuais",
    "visual_preferences",
    "consolidado_historico",
    "metadata",
    "raw_faturamento_upload",
    "raw_contabilidade_upload",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_sqlite_engine(db_path: str) -> Engine:
    """Create a SQLAlchemy engine for the local SQLite file."""
    path = Path(db_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found: {path}")
    return create_engine(f"sqlite:///{path}", echo=False)


def _build_pg_engine(pg_url: str) -> Engine:
    """Create a SQLAlchemy engine for the remote PostgreSQL database."""
    return create_engine(pg_url, echo=False)


def _get_sqlite_tables(engine: Engine) -> list[str]:
    """Return a list of user tables present in the SQLite database."""
    inspector = inspect(engine)
    return inspector.get_table_names()


def _row_count(engine: Engine, table: str) -> int:
    """Return the number of rows in *table* using a simple COUNT(*)."""
    with engine.connect() as conn:
        result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
        return result.scalar() or 0


def migrate_table(
    table: str,
    sqlite_engine: Engine,
    pg_engine: Engine,
) -> dict:
    """Migrate a single table from SQLite to PostgreSQL.

    Returns a dict with migration statistics for the summary report.
    """
    info: dict = {
        "table": table,
        "sqlite_rows": 0,
        "pg_rows": 0,
        "status": "OK",
        "error": None,
        "elapsed_s": 0.0,
    }

    t0 = time.perf_counter()

    # 1. Read from SQLite -----------------------------------------------
    print(f"\n{'=' * 60}")
    print(f"  Migrating table: {table}")
    print(f"{'=' * 60}")

    df = pd.read_sql_table(table, sqlite_engine)
    info["sqlite_rows"] = len(df)
    print(f"  SQLite  -> {len(df):>8,} rows read")

    if df.empty:
        print("  [WARN]  Table is empty - creating empty table in PostgreSQL.")

    # 2. Write to PostgreSQL (replace existing) -------------------------
    df.to_sql(
        name=table,
        con=pg_engine,
        if_exists="replace",
        index=False,
        method="multi",       # batch inserts for performance
        chunksize=5_000,      # avoid huge single statements
    )

    # 3. Verify row count in PostgreSQL ---------------------------------
    pg_count = _row_count(pg_engine, table)
    info["pg_rows"] = pg_count
    print(f"  Postgres -> {pg_count:>8,} rows written")

    if pg_count != len(df):
        print(f"  [WARN]  Row count mismatch! SQLite={len(df)}, PG={pg_count}")
        info["status"] = "MISMATCH"

    info["elapsed_s"] = time.perf_counter() - t0
    print(f"  [OK] Done in {info['elapsed_s']:.2f}s")
    return info


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_migration(
    db_path: str,
    pg_url: str,
    tables: Optional[List[str]] = None,
) -> None:
    """Execute the full migration pipeline."""

    # --- engines --------------------------------------------------------
    sqlite_engine = _build_sqlite_engine(db_path)
    pg_engine = _build_pg_engine(pg_url)

    # --- resolve table list ---------------------------------------------
    existing_sqlite_tables = _get_sqlite_tables(sqlite_engine)

    if tables:
        # Validate requested tables exist in SQLite
        missing = [t for t in tables if t not in existing_sqlite_tables]
        if missing:
            print(f"[WARN]  Tables not found in SQLite and will be skipped: {missing}")
        tables_to_migrate = [t for t in tables if t in existing_sqlite_tables]
    else:
        # Default: migrate all known tables that actually exist
        tables_to_migrate = [t for t in ALL_TABLES if t in existing_sqlite_tables]

        # Warn about unknown tables present in the database
        unknown = [t for t in existing_sqlite_tables if t not in ALL_TABLES]
        if unknown:
            print(f"[INFO]  Unknown tables in SQLite (not migrated): {unknown}")

    if not tables_to_migrate:
        print("[FAIL] No tables to migrate. Exiting.")
        sys.exit(1)

    print(f"\n[LIST] Tables to migrate ({len(tables_to_migrate)}): {tables_to_migrate}")

    # --- test PostgreSQL connection -------------------------------------
    try:
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] PostgreSQL connection OK")
    except Exception as exc:
        print(f"[FAIL] Cannot connect to PostgreSQL: {exc}")
        sys.exit(1)

    # --- migrate each table ---------------------------------------------
    results: list[dict] = []
    errors: list[dict] = []

    total_start = time.perf_counter()

    for table in tables_to_migrate:
        try:
            info = migrate_table(table, sqlite_engine, pg_engine)
            results.append(info)
        except Exception as exc:
            print(f"  [FAIL] ERROR migrating '{table}': {exc}")
            error_info = {
                "table": table,
                "sqlite_rows": "?",
                "pg_rows": 0,
                "status": "ERROR",
                "error": str(exc),
                "elapsed_s": 0.0,
            }
            results.append(error_info)
            errors.append(error_info)

    total_elapsed = time.perf_counter() - total_start

    # --- summary --------------------------------------------------------
    print("\n")
    print("=" * 70)
    print("  MIGRATION SUMMARY")
    print("=" * 70)
    print(f"  {'Table':<30} {'SQLite':>10} {'Postgres':>10} {'Status':<10} {'Time':>8}")
    print(f"  {'-' * 30} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

    for r in results:
        sqlite_str = f"{r['sqlite_rows']:>10,}" if isinstance(r["sqlite_rows"], int) else f"{'?':>10}"
        pg_str = f"{r['pg_rows']:>10,}" if isinstance(r["pg_rows"], int) else f"{'?':>10}"
        elapsed_str = f"{r['elapsed_s']:>7.2f}s"
        print(f"  {r['table']:<30} {sqlite_str} {pg_str} {r['status']:<10} {elapsed_str}")

    print(f"  {'-' * 30} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 8}")

    ok_count = sum(1 for r in results if r["status"] == "OK")
    err_count = len(errors)
    total_rows = sum(r["sqlite_rows"] for r in results if isinstance(r["sqlite_rows"], int))

    print(f"\n  Total tables : {len(results)}")
    print(f"  Succeeded    : {ok_count}")
    print(f"  Failed       : {err_count}")
    print(f"  Total rows   : {total_rows:,}")
    print(f"  Total time   : {total_elapsed:.2f}s")

    if errors:
        print("\n  [FAIL] ERRORS:")
        for e in errors:
            print(f"     - {e['table']}: {e['error']}")

    print("\n" + "=" * 70)

    if errors:
        print("[WARN]  Migration completed with errors. Review the table(s) above.")
        sys.exit(1)
    else:
        print("[DONE] Migration completed successfully!")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate data from a local SQLite database to a remote PostgreSQL instance.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # All tables
  python scripts/migrate_to_postgres.py \\
      --pg-url "postgresql://postgres:PASS@db.XXXXX.supabase.co:6543/postgres"

  # Specific tables only
  python scripts/migrate_to_postgres.py \\
      --db data/app.db \\
      --pg-url "postgresql://postgres:PASS@db.XXXXX.supabase.co:6543/postgres" \\
      --tables faturamento,contabilidade
        """,
    )
    parser.add_argument(
        "--db",
        default="data/app.db",
        help="Path to the SQLite database file (default: data/app.db)",
    )
    parser.add_argument(
        "--pg-url",
        required=True,
        help=(
            "PostgreSQL connection URL, e.g. "
            "postgresql://postgres:PASS@db.XXXXX.supabase.co:6543/postgres"
        ),
    )
    parser.add_argument(
        "--tables",
        default=None,
        help="Comma-separated list of tables to migrate (default: all)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    selected_tables = None
    if args.tables:
        selected_tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    run_migration(
        db_path=args.db,
        pg_url=args.pg_url,
        tables=selected_tables,
    )
