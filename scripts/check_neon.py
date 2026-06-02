"""Check the remote PostgreSQL database configured by environment variable.

Usage:
    set DATABASE_URL=postgresql://USER:PASSWORD@HOST/neondb?sslmode=require
    python scripts/check_neon.py

This script intentionally does not store credentials in source control.
"""

from __future__ import annotations

import os
import sys

import psycopg2


TABLES_TO_CHECK = [
    "base_dinamica",
    "faturamento",
    "contabilidade",
    "consolidado_historico",
    "de_para_unidades",
    "de_para_operadoras",
    "visual_preferences",
    "importacoes",
    "metadata",
]


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Defina DATABASE_URL antes de executar este script.")
        return 1

    conn = psycopg2.connect(database_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]
        print(f"Tabelas encontradas: {len(tables)}")
        for table_name in tables:
            print(f"  - {table_name}")

        print()
        for table_name in TABLES_TO_CHECK:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                print(f"  {table_name}: {cur.fetchone()[0]} linhas")
            except Exception as exc:
                print(f"  {table_name}: ERRO - {exc}")
                conn.rollback()
    finally:
        conn.close()

    print("\nTudo OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
