"""
db.py – Camada de abstração de banco de dados (dual-mode).

Detecta automaticamente se o ambiente é local (SQLite) ou cloud (PostgreSQL)
com base na presença de secrets do Streamlit. Todas as funções públicas operam
de forma transparente independentemente do backend.

Public API
----------
is_cloud, get_engine, get_con, read_table, write_table, append_table,
execute_sql, fetch_sql, table_columns, add_column, ensure_table,
sync_cloud_seed_if_newer
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caminhos padrão (modo local / SQLite)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "app.db"

# ---------------------------------------------------------------------------
# Detecção de modo (computada uma única vez no nível do módulo)
# ---------------------------------------------------------------------------

def _env_database_url() -> str:
    """Return the first PostgreSQL URL configured through environment variables."""
    for name in ("DATABASE_URL", "POSTGRES_URL", "NEON_DATABASE_URL"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _normalise_database_url(url: str) -> str:
    """Normalize provider URLs for SQLAlchemy."""
    url = str(url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _secret_bool(name: str, default: bool = False) -> bool:
    """Read a boolean flag from env or Streamlit secrets."""
    value = os.environ.get(name)
    if value is None:
        try:
            if name in st.secrets:
                value = st.secrets[name]
        except Exception:
            value = None
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}


def _detect_cloud() -> bool:
    """Detecta PostgreSQL por DATABASE_URL ou por secrets do Streamlit."""
    if _env_database_url():
        logger.info("Modo cloud detectado (PostgreSQL via DATABASE_URL).")
        return True
    try:
        secrets = st.secrets
        if "connections" in secrets and "postgresql" in secrets["connections"]:
            logger.info("Modo cloud detectado (PostgreSQL via Streamlit secrets).")
            return True
    except Exception:
        pass
    logger.info("Modo local detectado (SQLite em %s).", DB_PATH)
    return False


_CLOUD_MODE: bool = _detect_cloud()
_LAST_SYNCED_SEED_VERSION: str | None = None

# ---------------------------------------------------------------------------
# Funções públicas – modo
# ---------------------------------------------------------------------------

def is_cloud() -> bool:
    """Returns True if running with PostgreSQL (cloud), False for SQLite (local)."""
    return _CLOUD_MODE

# ---------------------------------------------------------------------------
# Engine (SQLAlchemy) – cacheado via @st.cache_resource
# ---------------------------------------------------------------------------

@st.cache_resource
def get_engine():
    """Returns a SQLAlchemy engine for the active backend.

    * **Cloud**: constrói a connection string a partir de
      ``DATABASE_URL``/``POSTGRES_URL`` ou ``st.secrets["connections"]["postgresql"]``.
      Suporta tanto ``connection_url`` (Neon) quanto chaves individuais.
    * **Local**: usa SQLite em ``data/app.db``.
    """
    from sqlalchemy import create_engine  # import tardio

    if _CLOUD_MODE:
        env_url = _env_database_url()
        if env_url:
            url = _normalise_database_url(env_url)
            logger.info("Criando engine PostgreSQL via DATABASE_URL.")
            return create_engine(url, pool_pre_ping=True)

        pg = st.secrets["connections"]["postgresql"]

        # Modo 1: URL completa (ex.: Neon)
        if "connection_url" in pg:
            url = _normalise_database_url(pg["connection_url"])
            logger.info("Criando engine PostgreSQL via connection_url.")
            engine = create_engine(url, pool_pre_ping=True)
        else:
            # Modo 2: chaves individuais (host, port, username, password, database)
            dialect = pg.get("dialect", "postgresql+psycopg2")
            user = pg["username"]
            password = pg["password"]
            host = pg["host"]
            port = pg.get("port", 5432)
            database = pg["database"]
            sslmode = pg.get("sslmode", "")
            url = f"{dialect}://{user}:{password}@{host}:{port}/{database}"
            if sslmode:
                url += f"?sslmode={sslmode}"
            logger.info("Criando engine PostgreSQL (%s@%s:%s/%s).", user, host, port, database)
            engine = create_engine(url, pool_pre_ping=True)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DB_PATH}"
        logger.info("Criando engine SQLite (%s).", DB_PATH)
        engine = create_engine(url)

    return engine

# ---------------------------------------------------------------------------
# Conexão raw
# ---------------------------------------------------------------------------

def get_con():
    """Returns a raw DB connection.

    * **SQLite**: ``sqlite3.connect(DB_PATH)``
    * **PostgreSQL**: ``engine.raw_connection()`` (psycopg2 connection)
    """
    if _CLOUD_MODE:
        return get_engine().raw_connection()
    # Modo local – conexão direta via sqlite3
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))

# ---------------------------------------------------------------------------
# Helpers internos – conversão de placeholders e tipos
# ---------------------------------------------------------------------------

def _convert_placeholders(sql: str) -> str:
    """Converte placeholders ``?`` → ``%s`` quando no modo PostgreSQL.

    Ignora ``?`` que aparecem dentro de strings literais (delimitadas por aspas
    simples).  Para uso genérico — não cobre 100% dos edge-cases de SQL, mas
    é suficiente para as queries da aplicação.
    """
    if not _CLOUD_MODE:
        return sql
    # Substitui '?' fora de strings literais
    result: list[str] = []
    in_string = False
    for char in sql:
        if char == "'" and not in_string:
            in_string = True
            result.append(char)
        elif char == "'" and in_string:
            in_string = False
            result.append(char)
        elif char == "?" and not in_string:
            result.append("%s")
        else:
            result.append(char)
    return "".join(result)


_TYPE_MAP_TO_PG: dict[str, str] = {
    "REAL": "DOUBLE PRECISION",
    # INTEGER e TEXT permanecem iguais
}


def _convert_ddl_types(sql: str) -> str:
    """Converte tipos SQLite para PostgreSQL em DDL (CREATE TABLE, ALTER TABLE).

    Substitui ``REAL`` → ``DOUBLE PRECISION`` de forma case-insensitive,
    preservando o restante da instrução.
    """
    if not _CLOUD_MODE:
        return sql
    # Substituição case-insensitive de tipos mapeados
    for sqlite_type, pg_type in _TYPE_MAP_TO_PG.items():
        # Usa word-boundary para não substituir parcialmente (ex.: "REALMENTE")
        pattern = rf"\b{sqlite_type}\b"
        sql = re.sub(pattern, pg_type, sql, flags=re.IGNORECASE)
    return sql

# ---------------------------------------------------------------------------
# CRUD de tabelas via DataFrame
# ---------------------------------------------------------------------------

def read_table(name: str) -> pd.DataFrame:
    """Read full table into a DataFrame. Returns empty DataFrame if table doesn't exist."""
    try:
        return pd.read_sql(f"SELECT * FROM {name}", get_engine())
    except Exception:
        logger.debug("Tabela '%s' não encontrada ou erro na leitura — retornando DataFrame vazio.", name)
        return pd.DataFrame()


def write_table(name: str, df: pd.DataFrame, mode: str = "replace") -> None:
    """Write DataFrame to table.

    Parameters
    ----------
    name : str
        Nome da tabela.
    df : pd.DataFrame
        Dados a gravar.
    mode : str
        ``'replace'`` (padrão) ou ``'append'``.
    """
    df.to_sql(name, get_engine(), index=False, if_exists=mode)
    logger.info("write_table('%s', mode='%s') – %d linhas gravadas.", name, mode, len(df))


def append_table(name: str, df: pd.DataFrame) -> None:
    """Shortcut for ``write_table(name, df, mode='append')``."""
    write_table(name, df, mode="append")

# ---------------------------------------------------------------------------
# Execução de SQL cru
# ---------------------------------------------------------------------------

def execute_sql(sql: str, params: Optional[tuple] = None, commit: bool = True):
    """Execute raw SQL statement.

    Accepts ``?``-style placeholders; they are auto-converted to ``%s`` for
    PostgreSQL.  Returns the cursor so callers can fetch results if needed.

    Parameters
    ----------
    sql : str
        Instrução SQL (pode usar ``?`` como placeholder em ambos os modos).
    params : tuple, optional
        Parâmetros para bind.
    commit : bool
        Se ``True``, faz commit após a execução.

    Returns
    -------
    cursor
        Cursor do banco — pode ser usado para fetchall() em SELECTs.
    """
    converted_sql = _convert_placeholders(sql)
    con = get_con()
    try:
        cur = con.cursor()
        if params:
            cur.execute(converted_sql, params)
        else:
            cur.execute(converted_sql)
        if commit:
            con.commit()
        return cur
    except Exception:
        # Em caso de erro, tenta rollback para não travar a conexão
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        # Fecha a conexão apenas no modo cloud (raw_connection é descartável).
        # No SQLite, cada chamada já cria uma conexão nova, então também fecha.
        try:
            if commit:
                con.close()
        except Exception:
            pass


def fetch_sql(sql: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """Execute SQL and return result as a DataFrame.

    Placeholder conversion (``?`` → ``%s``) is applied automatically for
    PostgreSQL.
    """
    converted_sql = _convert_placeholders(sql)
    try:
        return pd.read_sql(converted_sql, get_engine(), params=params)
    except Exception:
        logger.debug("fetch_sql falhou — retornando DataFrame vazio. SQL: %s", converted_sql[:200])
        return pd.DataFrame()

# ---------------------------------------------------------------------------
# Introspecção de schema
# ---------------------------------------------------------------------------

def table_columns(table_name: str) -> set[str]:
    """Return set of column names for a given table.

    * **SQLite** — usa ``PRAGMA table_info``.
    * **PostgreSQL** — consulta ``information_schema.columns``.
    """
    if _CLOUD_MODE:
        sql = (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s"
        )
        con = get_con()
        try:
            cur = con.cursor()
            cur.execute(sql, (table_name,))
            cols = {row[0] for row in cur.fetchall()}
        finally:
            con.close()
    else:
        con = get_con()
        try:
            cur = con.cursor()
            cur.execute(f"PRAGMA table_info({table_name})")
            # Cada row: (cid, name, type, notnull, dflt_value, pk)
            cols = {row[1] for row in cur.fetchall()}
        finally:
            con.close()

    logger.debug("table_columns('%s') → %s", table_name, cols)
    return cols

# ---------------------------------------------------------------------------
# Alteração de schema
# ---------------------------------------------------------------------------

def add_column(table_name: str, col_name: str, col_type: str = "TEXT") -> None:
    """ALTER TABLE ADD COLUMN, com mapeamento de tipos para PostgreSQL.

    Parameters
    ----------
    table_name : str
        Nome da tabela.
    col_name : str
        Nome da nova coluna.
    col_type : str
        Tipo da coluna (SQLite-style: ``REAL``, ``INTEGER``, ``TEXT``).
        Convertido automaticamente para PostgreSQL quando necessário.
    """
    # Mapeia tipo se necessário
    mapped_type = col_type
    if _CLOUD_MODE:
        mapped_type = _TYPE_MAP_TO_PG.get(col_type.upper(), col_type)

    sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {mapped_type}"
    logger.info("add_column: %s", sql)

    con = get_con()
    try:
        cur = con.cursor()
        cur.execute(sql)
        con.commit()
    except Exception as exc:
        # Ignora erro se a coluna já existe (comportamento idempotente)
        err_msg = str(exc).lower()
        if "duplicate column" in err_msg or "already exists" in err_msg:
            logger.debug("Coluna '%s' já existe em '%s' — ignorando.", col_name, table_name)
        else:
            try:
                con.rollback()
            except Exception:
                pass
            raise
    finally:
        con.close()

_ensured_tables: set[str] = set()  # cache para evitar chamadas repetidas


def ensure_table(create_sql: str) -> None:
    """Execute ``CREATE TABLE IF NOT EXISTS ...`` with automatic type conversion.

    Accepts SQLite-style DDL and converts types (e.g. ``REAL`` →
    ``DOUBLE PRECISION``) when running against PostgreSQL.

    Usa cache interno para evitar executar DDL repetido a cada rerun.
    """
    # Extrai nome da tabela para usar como chave de cache
    import re as _re
    match = _re.search(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)", create_sql, _re.IGNORECASE)
    table_key = match.group(1) if match else create_sql[:60]

    if table_key in _ensured_tables:
        return  # já garantida nesta sessão

    converted = _convert_ddl_types(create_sql)
    logger.info("ensure_table: %s", converted[:120])

    con = get_con()
    try:
        cur = con.cursor()
        cur.execute(converted)
        con.commit()
        _ensured_tables.add(table_key)
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Auto-migração: SQLite embarcado → PostgreSQL (executa uma vez no deploy)
# ---------------------------------------------------------------------------

_KNOWN_TABLES: list[str] = [
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
]

_SEED_SYNC_TABLES: list[str] = [
    "base_dinamica",
    "faturamento",
    "contabilidade",
    "metadata",
]


def auto_migrate_from_sqlite() -> None:
    """Migra dados do SQLite embarcado para PostgreSQL no primeiro deploy.

    Chamada apenas em modo cloud. Verifica se o PostgreSQL já possui a
    tabela ``base_dinamica`` — se sim, pula. Se não, copia tudo do SQLite.
    """
    if not _CLOUD_MODE:
        return

    # Verifica se já migrou
    try:
        cols = table_columns("base_dinamica")
        if cols:
            logger.info("auto_migrate: PostgreSQL ja possui tabelas — pulando.")
            return
    except Exception:
        pass

    if not DB_PATH.exists():
        logger.warning("auto_migrate: SQLite nao encontrado em %s.", DB_PATH)
        return

    logger.info("auto_migrate: Iniciando migracao SQLite -> PostgreSQL...")

    from sqlalchemy import create_engine as _sa_create_engine

    sqlite_engine = _sa_create_engine(f"sqlite:///{DB_PATH}")
    pg_engine = get_engine()

    migrated = 0
    errors = []

    for tbl in _KNOWN_TABLES:
        try:
            df = pd.read_sql(f"SELECT * FROM {tbl}", sqlite_engine)
            df.to_sql(tbl, pg_engine, index=False, if_exists="replace",
                      method="multi", chunksize=5_000)
            migrated += 1
            logger.info("auto_migrate: '%s' -> %d linhas.", tbl, len(df))
        except Exception as exc:
            if "no such table" in str(exc).lower():
                logger.debug("auto_migrate: '%s' nao existe no SQLite.", tbl)
            else:
                logger.error("auto_migrate: erro em '%s': %s", tbl, exc)
                errors.append(tbl)

    logger.info("auto_migrate: Concluido. %d tabelas, %d erros.", migrated, len(errors))


def _read_sqlite_metadata_value(key: str) -> str:
    if not DB_PATH.exists():
        return ""
    try:
        con = sqlite3.connect(str(DB_PATH))
        try:
            row = pd.read_sql(
                "SELECT valor FROM metadata WHERE chave = ?",
                con,
                params=(key,),
            )
            if row.empty:
                return ""
            return str(row["valor"].iloc[0] or "").strip()
        finally:
            con.close()
    except Exception:
        return ""


def _read_cloud_metadata_value(key: str) -> str:
    try:
        row = fetch_sql(
            "SELECT valor FROM metadata WHERE chave = ?",
            (key,),
        )
        if row.empty:
            return ""
        return str(row["valor"].iloc[0] or "").strip()
    except Exception:
        return ""


def sync_cloud_seed_if_newer() -> None:
    """Synchronize operational tables from embedded SQLite to PostgreSQL by version.

    This keeps Streamlit Cloud updated after a repository deploy without
    overwriting runtime-only tables such as visual preferences or comments.
    """
    global _LAST_SYNCED_SEED_VERSION

    if not _CLOUD_MODE or not DB_PATH.exists():
        return

    if not _secret_bool("SYNC_CLOUD_SEED", default=False):
        logger.info("seed sync: desativado. Defina SYNC_CLOUD_SEED=1 para sincronizar seed operacional.")
        return

    seed_version = _read_sqlite_metadata_value("base_seed_version")
    if not seed_version:
        return
    if _LAST_SYNCED_SEED_VERSION == seed_version:
        return

    cloud_version = _read_cloud_metadata_value("base_seed_version")
    if cloud_version == seed_version:
        logger.info("seed sync: PostgreSQL ja esta na versao %s.", seed_version)
        _LAST_SYNCED_SEED_VERSION = seed_version
        return

    logger.info("seed sync: atualizando PostgreSQL de '%s' para '%s'.", cloud_version, seed_version)
    from sqlalchemy import create_engine as _sa_create_engine

    sqlite_engine = _sa_create_engine(f"sqlite:///{DB_PATH}")
    pg_engine = get_engine()
    for tbl in _SEED_SYNC_TABLES:
        try:
            df = pd.read_sql(f"SELECT * FROM {tbl}", sqlite_engine)
            df.to_sql(tbl, pg_engine, index=False, if_exists="replace",
                      method="multi", chunksize=5_000)
            logger.info("seed sync: '%s' -> %d linhas.", tbl, len(df))
        except Exception as exc:
            logger.error("seed sync: erro em '%s': %s", tbl, exc)
            return
    _LAST_SYNCED_SEED_VERSION = seed_version
