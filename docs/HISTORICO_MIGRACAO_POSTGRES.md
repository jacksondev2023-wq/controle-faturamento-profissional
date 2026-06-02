# Histórico Completo da Migração para PostgreSQL

> **Data**: 02/06/2026  
> **Autor**: Assistente IA (Antigravity/Gemini)  
> **Objetivo**: Documentar todas as alterações feitas para resolver a perda de dados no deploy e migrar de SQLite para PostgreSQL.

---

## 1. Problema Original

### Sintoma
O app estava deployado no **Streamlit Community Cloud** (https://share.streamlit.io). Toda alteração feita em runtime — preferências visuais, comentários, importações, DE/PARA — era **perdida** quando o app reiniciava ou era redeployado.

### Causa Raiz
O Streamlit Community Cloud usa um **filesystem efêmero**. O arquivo `data/app.db` (SQLite) é recriado a partir do repositório Git a cada deploy. Qualquer escrita em disco durante runtime é descartada.

### Solução Implementada
Arquitetura **dual-mode**: o app detecta automaticamente o ambiente e usa o backend correto:
- **Local (desenvolvimento)**: SQLite em `data/app.db` — sem necessidade de credenciais ou internet.
- **Cloud (produção)**: PostgreSQL no **Neon.tech** — dados persistentes, backups automáticos.

---

## 2. Decisões Arquiteturais

### Por que Neon.tech e não Supabase?

Inicialmente tentamos o **Supabase**, mas ele apresentou dois problemas críticos:

1. **IPv6-only**: A conexão direta (`db.xxxxx.supabase.co`) resolve apenas para endereços IPv6. Nem a máquina local do desenvolvedor nem o Streamlit Community Cloud conseguiam conectar.
2. **Pooler não reconhecia o projeto**: O Supavisor (`aws-0-us-west-2.pooler.supabase.com`) retornava `FATAL: (ENOTFOUND) tenant/user postgres.xxxxx not found` — possivelmente por ser um projeto recém-criado no plano Free.

O **Neon.tech** foi escolhido como alternativa porque:
- Conexão **IPv4** nativa (sem problemas de rede)
- Plano gratuito com **0.5 GB** (mais que suficiente)
- PostgreSQL nativo (mesma API, sem mudanças de código)
- Região **São Paulo (sa-east-1)** disponível
- Cold-start de ~1-2s (aceitável)

### Por que dual-mode e não migração total?

Manter o SQLite local permite que o desenvolvedor rode o app **sem internet, sem credenciais** e sem depender de serviços externos. O modo é detectado automaticamente pela presença de `st.secrets["connections"]["postgresql"]`.

---

## 3. Estrutura do Projeto (Após Migração)

```
controle_faturamento_profissional/
├── app.py                          # App principal Streamlit (~3.856 linhas)
├── requirements.txt                # Dependências Python
├── render.yaml                     # Config de deploy (Render - não usado atualmente)
├── README.md                       # Documentação do projeto
├── .gitignore                      # Ignora secrets.toml, backups, etc.
│
├── .streamlit/
│   └── secrets.example.toml        # Template de credenciais (NÃO contém senhas reais)
│
├── src/
│   ├── db.py                       # ⭐ NOVO: Camada de abstração de banco dual-mode
│   └── etl.py                      # Lógica de ETL (limpeza, normalização, DE/PARA)
│
├── scripts/
│   ├── seed_database.py            # Cria data/app.db com dados iniciais
│   ├── migrate_to_postgres.py      # ⭐ NOVO: Script de migração SQLite → PostgreSQL
│   ├── import_dinamica_base.py     # Importação da base dinâmica
│   └── check_neon.py               # ⭐ NOVO: Script de verificação do Neon (temporário)
│
├── data/
│   ├── app.db                      # Banco SQLite local (commitado no Git)
│   └── raw/                        # Arquivos Excel brutos (não commitados)
│
└── docs/
    ├── CODEX_CONTEXT.md            # Contexto de negócio para IAs
    ├── PROJETO_CONTROLE_FATURAMENTO.md  # Documentação técnica do projeto
    └── HISTORICO_MIGRACAO_POSTGRES.md   # ⭐ ESTE ARQUIVO
```

---

## 4. Arquivos Criados e Modificados

### 4.1. `src/db.py` (NOVO — 451 linhas)

**Propósito**: Camada de abstração que encapsula todo acesso ao banco de dados.

**Detecção de modo** (linhas 40-55):
```python
def _detect_cloud() -> bool:
    # Verifica st.secrets["connections"]["postgresql"]
    # Se presente → PostgreSQL (cloud)
    # Se ausente → SQLite (local)
```
A variável `_CLOUD_MODE` é computada uma vez no nível do módulo.

**Engine SQLAlchemy** (linhas 69-108):
- Usa `@st.cache_resource` para evitar recriar a cada rerun.
- Suporta dois formatos de secrets:
  - `connection_url`: URL completa (usado pelo Neon)
  - Chaves individuais: `host`, `port`, `username`, `password`, `database` (usado pelo Supabase)

**API pública** (11 funções):

| Função | Descrição |
|--------|-----------|
| `is_cloud()` | Retorna `True` se PostgreSQL, `False` se SQLite |
| `get_engine()` | Engine SQLAlchemy cacheado |
| `get_con()` | Conexão raw (sqlite3 ou psycopg2) |
| `read_table(name)` | Tabela inteira → DataFrame |
| `write_table(name, df, mode)` | DataFrame → tabela (`replace` ou `append`) |
| `append_table(name, df)` | Atalho para `write_table(..., 'append')` |
| `execute_sql(sql, params, commit)` | SQL cru com conversão `?` → `%s` |
| `fetch_sql(sql, params)` | SQL → DataFrame com conversão de placeholders |
| `table_columns(table_name)` | Set de nomes de colunas (PRAGMA ou information_schema) |
| `add_column(table, col, type)` | ALTER TABLE com mapeamento REAL→DOUBLE PRECISION |
| `ensure_table(create_sql)` | CREATE TABLE IF NOT EXISTS com cache e conversão de tipos |
| `sync_cloud_seed_if_newer()` | Sincroniza tabelas operacionais do SQLite embarcado para PostgreSQL por `base_seed_version` |

**Conversões automáticas**:
- **Placeholders**: `?` → `%s` no modo PostgreSQL (parser character-level que ignora `?` dentro de strings)
- **Tipos DDL**: `REAL` → `DOUBLE PRECISION` (regex com word-boundary)
- **Cache de ensure_table**: Usa set `_ensured_tables` para evitar DDL repetido

**Auto-migração** (linhas 393-451):
- Função `auto_migrate_from_sqlite()` chamada no startup do app
- Verifica se PostgreSQL está vazio (checa `table_columns("base_dinamica")`)
- Se vazio, lê do SQLite embarcado (`data/app.db`) e copia 11 tabelas para PostgreSQL
- Idempotente: não executa se tabelas já existem

### 4.2. `app.py` (MODIFICADO — 3.856 linhas)

**Mudanças realizadas**:

1. **Removido** `import sqlite3` (linha 7 original)

2. **Adicionado** bloco de imports do `src.db` (linhas 28-42):
   ```python
   from src.db import (
       get_con as _db_get_con,
       read_table as _db_read_table,
       write_table as _db_write_table,
       append_table as _db_append_table,
       execute_sql as _db_execute_sql,
       fetch_sql as _db_fetch_sql,
       table_columns as _db_table_columns,
       add_column as _db_add_column,
       ensure_table as _db_ensure_table,
       is_cloud as _db_is_cloud,
       auto_migrate_from_sqlite as _db_auto_migrate,
       DB_PATH,
   )
   ```

3. **Substituídas 13 funções** que usavam `sqlite3` diretamente:

   | Função | Antes | Depois |
   |--------|-------|--------|
   | `get_con()` | `sqlite3.connect(DB_PATH)` | `_db_get_con()` |
   | `init_db_if_needed()` | `if not DB_PATH.exists()` | `if not _db_is_cloud() and not DB_PATH.exists()` |
   | `read_table()` | `pd.read_sql()` manual | `_db_read_table()` |
   | `write_table()` | `df.to_sql()` manual | `_db_write_table()` |
   | `append_table()` | wrapper manual | `_db_append_table()` |
   | `ensure_visual_preferences_table()` | `con.execute(CREATE TABLE)` | `_db_ensure_table()` + índice UNIQUE |
   | `load_visual_preference()` | `pd.read_sql()` com params | `_db_fetch_sql()` |
   | `save_visual_preference()` | `ON CONFLICT` upsert | DELETE + INSERT (compatível PG) |
   | `delete_visual_preference()` | `con.execute(DELETE)` | `_db_execute_sql()` |
   | `ensure_base_dinamica_table()` | `PRAGMA table_info` | `_db_table_columns()` + `_db_add_column()` |
   | `ensure_importacoes_table()` | `con.execute(CREATE TABLE)` | `_db_ensure_table()` |
   | `ensure_exportacoes_table()` | `PRAGMA table_info` + `rowid` | `_db_table_columns()` + `_db_fetch_sql()` |
   | `ensure_inconsistencias_table()` | `con.execute(CREATE TABLE)` | `_db_ensure_table()` |
   | `ensure_comentarios_table()` | `con.execute(CREATE TABLE)` | `_db_ensure_table()` |
   | `file_already_imported()` | `pd.read_sql()` com params | `_db_fetch_sql()` |

4. **Adicionada chamada** `_db_auto_migrate()` após `init_db_if_needed()` (linha 3697)

5. **Removida dependência de `rowid`**: O PostgreSQL não tem `rowid` implícito. A função `ensure_exportacoes_table()` foi reescrita para usar `data_hora` + `nome_arquivo` como identificadores no UPDATE.

### 4.3. `scripts/migrate_to_postgres.py` (NOVO — 311 linhas)

Script CLI para migração one-time. Aceita argumentos:
- `--db`: caminho do SQLite (default: `data/app.db`)
- `--pg-url`: URL do PostgreSQL (obrigatório)
- `--tables`: lista de tabelas separadas por vírgula (default: todas)

Migra 11 tabelas com verificação de row count, batched inserts (`chunksize=5000`), e relatório final formatado.

### 4.4. `.streamlit/secrets.example.toml` (NOVO)

Template para credenciais. Formato Neon:
```toml
[connections.postgresql]
connection_url = "postgresql://USER:PASSWORD@ep-XXXX.sa-east-1.aws.neon.tech/neondb?sslmode=require"
```

### 4.5. `requirements.txt` (MODIFICADO)

Adicionadas duas dependências:
```
sqlalchemy>=2.0
psycopg2-binary>=2.9
```

### 4.6. `.gitignore` (MODIFICADO)

Adicionada linha:
```
.streamlit/secrets.toml
```

---

## 5. Banco de Dados

### 5.1. Tabelas (11 no total)

| Tabela | Linhas | Descrição |
|--------|--------|-----------|
| `base_dinamica` | 141 | Base consolidada de faturamento/recebimento |
| `faturamento` | 231 | Dados brutos de faturamento importados |
| `contabilidade` | 259 | Dados brutos de recebimento/contabilidade |
| `de_para_unidades` | 48 | Mapeamento nome original → nome padrão (unidades) |
| `de_para_operadoras` | 72 | Mapeamento nome original → nome padrão (operadoras) |
| `comentarios_manuais` | 0 | Comentários por unidade/operadora/mês |
| `importacoes` | 4 | Log de uploads realizados |
| `exportacoes` | 0 | Log de exportações para Excel |
| `inconsistencias_manuais` | 0 | Inconsistências identificadas e tratadas |
| `visual_preferences` | 3 | Preferências de visualização do dashboard |
| `consolidado_historico` | 1.260 | Snapshot mensal do consolidado |

### 5.2. Credenciais Neon (Produção)

> Credenciais reais não devem ficar em arquivos versionados. Configure a URL de conexão apenas nos Secrets do Streamlit Cloud ou em `.streamlit/secrets.toml` local, que deve permanecer ignorado pelo Git.

| Campo | Valor |
|-------|-------|
| **Provider** | Neon.tech |
| **Host / Database / User / Password** | Armazenados somente em secrets |
| **SSL** | `sslmode=require` |
| **Região sugerida** | São Paulo (sa-east-1) |
| **Plano** | Free (0.5 GB) |

### 5.3. Secrets no Streamlit Cloud

Configurados em: **share.streamlit.io** → App → Settings → Secrets

```toml
[connections.postgresql]
connection_url = "postgresql://USUARIO:SENHA@HOST/neondb?sslmode=require"
```

---

## 6. Problemas Encontrados e Soluções

### 6.1. IPv6 no Supabase
- **Problema**: `db.xxxxx.supabase.co` resolve apenas para IPv6. O psycopg2 no Windows retorna `could not translate host name`.
- **Solução**: Migrado para Neon.tech (IPv4 nativo).

### 6.2. Supabase Pooler "tenant not found"
- **Problema**: `aws-0-us-west-2.pooler.supabase.com` retornava `FATAL: (ENOTFOUND) tenant/user postgres.xxxxx not found`.
- **Solução**: Abandonado Supabase em favor do Neon.

### 6.3. Unicode no terminal Windows
- **Problema**: Emojis (⚠✓❌) no `migrate_to_postgres.py` causavam `UnicodeEncodeError` com codec `cp1252`.
- **Solução**: Substituídos por tags ASCII (`[WARN]`, `[OK]`, `[FAIL]`, etc.).

### 6.4. `ON CONFLICT` sem PRIMARY KEY
- **Problema**: A migração via `df.to_sql()` (pandas) não preserva constraints (PRIMARY KEY, UNIQUE). O `save_visual_preference()` usava `ON CONFLICT(pref_key) DO UPDATE SET` que falhava com `psycopg2.errors.InvalidColumnReference`.
- **Solução**: 
  1. Adicionado `CREATE UNIQUE INDEX IF NOT EXISTS` no `ensure_visual_preferences_table()`.
  2. Reativado UPSERT atomico para salvar preferencias.
  3. Adicionado fallback DELETE + INSERT para bases antigas sem indice aplicado.

### 6.5. Lentidão no carregamento
- **Problema**: Cada `ensure_*_table()` abria uma conexão nova ao Neon (~200ms cada, cold start ~1-2s).
- **Solução**: Cache `_ensured_tables` em `ensure_table()` — cada tabela só é verificada 1x por sessão. O app tambem cacheia leituras de tabelas operacionais por 5 minutos e invalida o cache apos gravacoes.

### 6.6. `rowid` inexistente no PostgreSQL
- **Problema**: `ensure_exportacoes_table()` usava `SELECT rowid, ... FROM exportacoes` e `UPDATE ... WHERE rowid = ?`. PostgreSQL não tem `rowid` implícito.
- **Solução**: Reescrito para usar `data_hora` + `nome_arquivo` como chave de UPDATE.

### 6.7. Atualizacao da base operacional em producao
- **Problema**: Depois do primeiro deploy, o PostgreSQL ja populado nao era atualizado automaticamente quando `data/app.db` recebia uma nova base validada.
- **Solução**: Criado `metadata.base_seed_version` e `sync_cloud_seed_if_newer()`. No cloud, o app substitui somente tabelas operacionais (`base_dinamica`, `faturamento`, `contabilidade`, `metadata`) quando a versao embarcada e mais nova/diferente. Preferencias, comentarios, DE/PARA e historicos de uso nao sao apagados.

---

## 7. Commits Realizados

```
6b81f42 Fix ON CONFLICT erro no PostgreSQL e otimizar cache de ensure_table
f73b78b Suportar Neon via connection_url e corrigir IPv6
e9b71f8 Migrar para PostgreSQL com dual-mode e auto-migracao no deploy
f865958 Persistir preferencias de visualizacao
0f0052e Primeira versao do controle de faturamento
```

---

## 8. Deploy

### Ambiente de produção
- **Plataforma**: Streamlit Community Cloud (share.streamlit.io)
- **URL do app**: `https://controle-faturamento-profissional.streamlit.app`
- **Repositório**: `https://github.com/jacksondev2023-wq/controle-faturamento-profissional`
- **Branch**: `main`
- **Auto-deploy**: Sim (a cada push no `main`)

### Fluxo de deploy
1. Desenvolvedor faz alterações locais (SQLite)
2. `git push origin main`
3. Streamlit Cloud detecta o push e redeploya
4. App inicia, detecta `st.secrets` → modo PostgreSQL
5. `auto_migrate_from_sqlite()` verifica se PG está populado; se não, migra do SQLite embarcado
6. App roda normalmente com dados persistentes no Neon

---

## 9. Como Rodar Localmente

```bash
# Instalar dependências
pip install -r requirements.txt

# Criar banco inicial (se data/app.db não existir)
python scripts/seed_database.py

# Rodar o app (usa SQLite automaticamente)
streamlit run app.py
```

Não precisa de credenciais ou internet para desenvolvimento local.

---

## 10. Problemas Conhecidos / Pendentes

### 10.1. Lentidão residual
O primeiro carregamento após o Neon "dormir" (inatividade >5 min no plano Free) leva ~2-3s extra (cold start). Carregamentos subsequentes são normais. Possível melhoria: usar connection pooling com `pool_size` maior no SQLAlchemy.

### 10.2. Supabase abandonado mas conta existe
O projeto Supabase criado durante os testes ficou vazio e pode ser deletado. Como credenciais chegaram a ser compartilhadas durante a configuração, qualquer senha/token relacionado deve ser rotacionado antes de reutilizar a conta.

### 10.3. Script check_neon.py
O arquivo `scripts/check_neon.py` foi mantido como utilitario seguro. Ele nao armazena credenciais; usa somente a variavel de ambiente `DATABASE_URL`.

### 10.4. `data/app.db` no Git
O SQLite continua commitado no repositório. Isso é intencional: serve como fallback para dev local e como fonte para a auto-migração no primeiro deploy cloud. Porém, como ele não é atualizado em produção, dados novos inseridos via app no cloud **não refletem** no SQLite do repositório.

### 10.5. Falta de `__init__.py` no `src/`
O pacote `src` não tem `__init__.py`. Funciona no Streamlit porque o Python adiciona o diretório raiz ao `sys.path`, mas pode causar problemas em outros contextos.

### 10.6. Todas as tabelas perderam constraints na migração
O `df.to_sql()` do pandas não preserva PRIMARY KEY, UNIQUE, NOT NULL, etc. Apenas `visual_preferences` teve o índice UNIQUE recriado. Se outras tabelas precisarem de constraints, devem ser adicionadas manualmente via `execute_sql()` no `ensure_*_table()`.

---

## 11. Referência Rápida de Comandos

```bash
# Migrar dados locais para PostgreSQL (one-time)
python scripts/migrate_to_postgres.py \
    --pg-url "$DATABASE_URL"

# Verificar dados no Neon
python scripts/check_neon.py

# Compilar para verificar sintaxe
python -m compileall app.py src scripts -q

# Deploy
git add -A
git commit -m "descricao"
git push origin main
```
