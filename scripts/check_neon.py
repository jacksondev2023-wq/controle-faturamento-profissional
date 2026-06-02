import psycopg2

conn = psycopg2.connect(
    "postgresql://neondb_owner:npg_k4xfwu5sPvDc@ep-cold-tree-acuzzeuv.sa-east-1.aws.neon.tech/neondb?sslmode=require"
)
cur = conn.cursor()

# Listar tabelas
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [r[0] for r in cur.fetchall()]
print(f"Tabelas encontradas: {len(tables)}")
for t in tables:
    print(f"  - {t}")

# Contar linhas das principais
print()
for tbl in ["base_dinamica", "faturamento", "contabilidade", "consolidado_historico", "de_para_unidades", "de_para_operadoras", "visual_preferences", "importacoes"]:
    try:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        print(f"  {tbl}: {cur.fetchone()[0]} linhas")
    except Exception as e:
        print(f"  {tbl}: ERRO - {e}")
        conn.rollback()

conn.close()
print("\nTudo OK!")
