
from pathlib import Path
from datetime import datetime
import hashlib
import sqlite3
import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.etl import (
    DEFAULT_DEPARA,
    DEFAULT_OPERADORA_DEPARA,
    read_first_sheet,
    prepare_faturamento,
    prepare_contabilidade,
    prepare_consolidado_historico,
)

DB_PATH = ROOT / "data" / "app.db"
RAW = ROOT / "data" / "raw"

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""

def seed_database():
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)

    depara = DEFAULT_DEPARA.copy()
    depara.to_sql("de_para_unidades", con, index=False, if_exists="replace")
    depara_operadoras = DEFAULT_OPERADORA_DEPARA.copy()
    depara_operadoras.to_sql("de_para_operadoras", con, index=False, if_exists="replace")

    fat_path = RAW / "faturamento_abril_2026.xlsx"
    cont_path = RAW / "contabilidade_abril_maio_2026.xlsx"
    hist_mar_path = RAW / "modelo_historico_fat_mar_rec_mar_abr.xlsx"
    hist_abr_path = RAW / "relatorio_atual_fat_abr_rec_abr_mai.xlsx"

    if fat_path.exists():
        fat_raw = read_first_sheet(fat_path)
        fat_raw.to_sql("raw_faturamento_upload", con, index=False, if_exists="replace")
        fat = prepare_faturamento(fat_raw, depara, depara_operadoras=depara_operadoras, fallback_year=2026, origem=fat_path.name)
        fat.to_sql("faturamento", con, index=False, if_exists="replace")

    if cont_path.exists():
        cont_raw = read_first_sheet(cont_path)
        cont_raw.to_sql("raw_contabilidade_upload", con, index=False, if_exists="replace")
        cont = prepare_contabilidade(cont_raw, depara, depara_operadoras=depara_operadoras, fallback_year=2026, origem=cont_path.name)
        cont.to_sql("contabilidade", con, index=False, if_exists="replace")

    importacoes = []
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    if fat_path.exists():
        importacoes.append({
            "data_hora": now,
            "tipo_arquivo": "Faturamento IW",
            "nome_arquivo": fat_path.name,
            "mes_ano_identificado": "Abr/2026",
            "qtd_linhas": len(fat) if "fat" in locals() else 0,
            "status": "Base inicial",
            "usuario": "sistema",
            "detalhes": "Registro criado pelo seed inicial.",
            "hash_arquivo": file_hash(fat_path),
        })
    if cont_path.exists():
        importacoes.append({
            "data_hora": now,
            "tipo_arquivo": "Contabilidade/Recebimentos",
            "nome_arquivo": cont_path.name,
            "mes_ano_identificado": "Abr/2026, Mai/2026",
            "qtd_linhas": len(cont) if "cont" in locals() else 0,
            "status": "Base inicial",
            "usuario": "sistema",
            "detalhes": "Registro criado pelo seed inicial.",
            "hash_arquivo": file_hash(cont_path),
        })
    pd.DataFrame(importacoes, columns=[
        "data_hora", "tipo_arquivo", "nome_arquivo", "mes_ano_identificado",
        "qtd_linhas", "status", "usuario", "detalhes", "hash_arquivo",
    ]).to_sql("importacoes", con, index=False, if_exists="replace")

    historicos = []
    for path in [hist_mar_path, hist_abr_path]:
        if path.exists():
            df = read_first_sheet(path)
            hist = prepare_consolidado_historico(df, origem=path.name)
            if not hist.empty:
                historicos.append(hist)
    if historicos:
        pd.concat(historicos, ignore_index=True).to_sql("consolidado_historico", con, index=False, if_exists="replace")

    # Tabela para comentários manuais, separada das bases.
    pd.DataFrame(columns=[
        "unidade_padrao", "operadora_padrao", "mes_referencia", "ano_referencia",
        "comentario_manual", "atualizado_por", "atualizado_em"
    ]).to_sql("comentarios_manuais", con, index=False, if_exists="replace")

    # Metadados do projeto.
    pd.DataFrame([
        {"chave": "projeto", "valor": "Controle Faturamento x Recebimento"},
        {"chave": "observacao", "valor": "Base inicial criada com arquivos enviados no ChatGPT."},
        {"chave": "limite_marco", "valor": "Março existe como histórico consolidado. Para rastreio completo, importar faturamento/contabilidade brutos de março."},
    ]).to_sql("metadata", con, index=False, if_exists="replace")

    con.close()
    print(f"Base criada em: {DB_PATH}")

if __name__ == "__main__":
    seed_database()
