from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.etl import DINAMICA_COLUMNS, dinamica_to_raw_tables, norm_text, parse_dinamica_workbook

DB_PATH = ROOT / "data" / "app.db"


def write_table(con: sqlite3.Connection, name: str, df: pd.DataFrame):
    df.to_sql(name, con, index=False, if_exists="replace")


def read_table(con: sqlite3.Connection, name: str) -> pd.DataFrame:
    try:
        return pd.read_sql(f"SELECT * FROM {name}", con)
    except Exception:
        return pd.DataFrame()


def normalize_depara(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["sigla_origem", "nome_padrao"]:
        if col not in df:
            df[col] = ""
    out = df[["sigla_origem", "nome_padrao"]].fillna("").astype(str)
    out["sigla_origem"] = out["sigla_origem"].str.strip()
    out["nome_padrao"] = out["nome_padrao"].str.strip()
    out = out[out["sigla_origem"] != ""].copy()
    out["_key"] = out["sigla_origem"].apply(norm_text)
    return out.drop_duplicates(subset="_key", keep="first").drop(columns="_key").reset_index(drop=True)


def normalize_base(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy() if df is not None else pd.DataFrame(columns=DINAMICA_COLUMNS)
    for col in DINAMICA_COLUMNS:
        if col not in out:
            out[col] = 0 if col not in {"unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao", "sinal_diretoria", "observacao", "origem_arquivo", "atualizado_em"} else ""
    out = out[DINAMICA_COLUMNS].copy()
    numeric_cols = [
        "linha_origem", "alerta_diretoria", "faturado_marco", "faturado_abril", "rec_bruto_marco", "rec_liquido_marco",
        "rec_bruto_abril", "rec_liquido_abril", "rec_bruto_maio", "rec_liquido_maio",
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    for col in [c for c in DINAMICA_COLUMNS if c not in numeric_cols]:
        out[col] = out[col].fillna("").astype(str).str.strip()
    return out[(out["unidade_original"] != "") & (out["operadora_original"] != "")].reset_index(drop=True)


def merge_base(existing: pd.DataFrame, incoming: pd.DataFrame, columns: list[str], source_name: str) -> pd.DataFrame:
    existing = normalize_base(existing)
    incoming = normalize_base(incoming)
    if existing.empty:
        return incoming
    out = existing.copy()
    out["_key"] = out["unidade_padrao"].apply(norm_text) + "||" + out["operadora_padrao"].apply(norm_text)
    incoming["_key"] = incoming["unidade_padrao"].apply(norm_text) + "||" + incoming["operadora_padrao"].apply(norm_text)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    for _, row in incoming.iterrows():
        key = row["_key"]
        mask = out["_key"] == key
        if mask.any():
            idx = out.index[mask][0]
            for col in columns:
                if col == "observacao":
                    new_obs = str(row.get("observacao", "") or "").strip()
                    old_obs = str(out.loc[idx, "observacao"] or "").strip()
                    if new_obs and new_obs not in old_obs:
                        out.loc[idx, "observacao"] = f"{old_obs} | {new_obs}" if old_obs else new_obs
                elif col in out:
                    out.loc[idx, col] = row.get(col, out.loc[idx, col])
            out.loc[idx, "origem_arquivo"] = source_name
            out.loc[idx, "atualizado_em"] = now
        else:
            new_row = {col: row.get(col, 0) for col in DINAMICA_COLUMNS}
            for col in DINAMICA_COLUMNS:
                if col not in columns and col not in {"linha_origem", "unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao", "alerta_diretoria", "sinal_diretoria", "origem_arquivo", "atualizado_em"}:
                    new_row[col] = "" if col == "observacao" else 0
            new_row["origem_arquivo"] = source_name
            new_row["atualizado_em"] = now
            out = pd.concat([out, pd.DataFrame([new_row])], ignore_index=True)
    return normalize_base(out.drop(columns="_key", errors="ignore"))


def ensure_importacoes(con: sqlite3.Connection):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS importacoes (
            data_hora TEXT,
            tipo_arquivo TEXT,
            nome_arquivo TEXT,
            mes_ano_identificado TEXT,
            qtd_linhas INTEGER,
            status TEXT,
            usuario TEXT,
            detalhes TEXT,
            hash_arquivo TEXT
        )
        """
    )
    cols = {row[1] for row in con.execute("PRAGMA table_info(importacoes)").fetchall()}
    if "hash_arquivo" not in cols:
        con.execute("ALTER TABLE importacoes ADD COLUMN hash_arquivo TEXT")


def backup_db() -> Path | None:
    if not DB_PATH.exists():
        return None
    backup_dir = ROOT / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"app_before_dinamica_{stamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def import_dinamica(path: Path, year: int = 2026, mode: str = "replace", columns: list[str] | None = None) -> dict[str, object]:
    backup_path = backup_db()
    base = parse_dinamica_workbook(path, origem=path.name)
    for col in DINAMICA_COLUMNS:
        if col not in base:
            base[col] = ""
    base = base[DINAMICA_COLUMNS].copy()

    con = sqlite3.connect(DB_PATH)
    try:
        if mode == "merge":
            base = merge_base(read_table(con, "base_dinamica"), base, columns or [], path.name)
        elif columns:
            keep = set(columns) | {"linha_origem", "unidade_original", "unidade_padrao", "operadora_original", "operadora_padrao", "origem_arquivo", "atualizado_em"}
            for col in DINAMICA_COLUMNS:
                if col not in keep:
                    base[col] = "" if col == "observacao" else 0
        fat, cont = dinamica_to_raw_tables(base, year=year, origem=path.name)
        write_table(con, "base_dinamica", base)
        write_table(con, "faturamento", fat)
        write_table(con, "contabilidade", cont)

        current_units = read_table(con, "de_para_unidades")
        current_ops = read_table(con, "de_para_operadoras")
        units = pd.concat(
            [
                base[["unidade_original", "unidade_padrao"]].rename(
                    columns={"unidade_original": "sigla_origem", "unidade_padrao": "nome_padrao"}
                ),
                current_units,
            ],
            ignore_index=True,
        )
        ops = pd.concat(
            [
                base[["operadora_original", "operadora_padrao"]].rename(
                    columns={"operadora_original": "sigla_origem", "operadora_padrao": "nome_padrao"}
                ),
                current_ops,
            ],
            ignore_index=True,
        )
        write_table(con, "de_para_unidades", normalize_depara(units))
        write_table(con, "de_para_operadoras", normalize_depara(ops))

        ensure_importacoes(con)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        import_row = pd.DataFrame(
            [
                {
                    "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "tipo_arquivo": "Base consolidada DINAMICA",
                    "nome_arquivo": path.name,
                    "mes_ano_identificado": "Fat: Mar/Abr/2026 | Rec: Abr/Mai/2026",
                    "qtd_linhas": len(base),
                    "status": "Base substituída",
                    "usuario": "sistema",
                    "detalhes": f"Importação via script. {len(fat)} linhas de faturamento e {len(cont)} linhas de recebimento geradas.",
                    "hash_arquivo": file_hash,
                }
            ]
        )
        import_row.to_sql("importacoes", con, index=False, if_exists="append")
        con.commit()
    finally:
        con.close()

    return {
        "backup": backup_path,
        "base_rows": len(base),
        "fat_rows": len(fat),
        "cont_rows": len(cont),
        "observations": int(base["observacao"].fillna("").astype(str).str.strip().ne("").sum()),
    }


def main():
    parser = argparse.ArgumentParser(description="Importa a aba DINAMICA como base principal do sistema.")
    parser.add_argument("arquivo", type=Path)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--mode", choices=["replace", "merge"], default="replace")
    parser.add_argument("--columns", default="", help="Lista separada por vírgula das colunas da base_dinamica a importar.")
    args = parser.parse_args()
    columns = [part.strip() for part in args.columns.split(",") if part.strip()]
    result = import_dinamica(args.arquivo, args.year, mode=args.mode, columns=columns)
    print(result)


if __name__ == "__main__":
    main()
