# Deploy profissional do portal

Este projeto deve rodar em producao com:

- codigo versionado no GitHub;
- aplicacao publicada no Render;
- dados persistidos em PostgreSQL externo;
- senha de acesso configurada fora do codigo.

## Por que nao usar SQLite em producao

O arquivo `data/app.db` funciona bem localmente, mas nao e o banco ideal para varias pessoas usando o portal. Em deploys cloud, arquivos locais podem ser recriados em novo deploy/reinicio e isso colocaria em risco observacoes, semaforos e edicoes feitas durante a apresentacao.

Em producao, use PostgreSQL via `DATABASE_URL`.

## Variaveis obrigatorias no Render

Configure no painel do Render, em Environment:

```text
DATABASE_URL=postgresql://...
APP_PASSWORD=senha-forte-do-portal
SYNC_CLOUD_SEED=0
```

`DATABASE_URL` deve apontar para Neon, Supabase, Render PostgreSQL ou outro PostgreSQL gerenciado.

`APP_PASSWORD` libera a tela de login simples do portal. Sem essa variavel, o app abre sem senha, comportamento usado apenas para desenvolvimento local.

`SYNC_CLOUD_SEED=0` protege o banco cloud contra sobrescrita automatica a cada deploy. Atualizacoes de base devem ser feitas pelo proprio portal ou por migracao controlada.

## Migrar o banco local para PostgreSQL

Depois de criar o banco PostgreSQL, rode localmente:

```powershell
python scripts/migrate_to_postgres.py --db data/app.db --pg-url "postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require"
```

O script copia as tabelas do SQLite local para o PostgreSQL e valida a quantidade de linhas.

## Publicar a versao

Depois que o PostgreSQL estiver configurado e migrado:

```powershell
git add app.py src/db.py src/etl.py src/acerto_contas.py src/consolidado_component.py scripts/import_dinamica_base.py scripts/migrate_to_postgres.py requirements.txt render.yaml docs/DEPLOY_PROFISSIONAL.md
git commit -m "Preparar deploy profissional com Postgres"
git push origin main
```

O Render esta configurado com `autoDeploy: true`, entao o push na branch `main` inicia a publicacao automaticamente.

## Cuidados

- Nao versionar `.streamlit/secrets.toml`.
- Nao publicar credenciais no GitHub.
- Preferir repositorio privado por conter regra de negocio e dados financeiros.
- Nao depender de `data/app.db` como banco de producao.
- Fazer backup do PostgreSQL antes de grandes importacoes.
