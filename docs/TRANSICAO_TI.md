# Transicao futura para TI

Este documento organiza o projeto para que, no futuro, a TI consiga migrar o portal para a infraestrutura corporativa sem depender de conhecimento informal.

## Estado atual planejado

O projeto esta preparado para dois modos:

- **Local/desenvolvimento**: usa SQLite em `data/app.db`.
- **Producao temporaria/profissional**: usa PostgreSQL via variavel `DATABASE_URL`.

Esse desenho e intencional. O Render/PostgreSQL funciona como etapa intermediaria para colocar o portal em uso por outras pessoas, mas sem prender o projeto a uma estrutura definitiva. Quando a TI assumir, a troca principal sera a `DATABASE_URL`.

## Principio de arquitetura

O codigo da aplicacao nao deve conter credenciais, caminhos internos da empresa ou configuracoes fixas de producao.

Configuracoes externas devem vir por variaveis de ambiente:

```text
DATABASE_URL
APP_PASSWORD
SYNC_CLOUD_SEED
```

No futuro, a TI pode substituir `DATABASE_URL` por uma URL de banco corporativo, sem alterar a logica principal do sistema.

## Componentes principais

| Componente | Responsabilidade |
|---|---|
| `app.py` | Interface Streamlit, telas, filtros, importacoes, exportacoes e edicoes no portal |
| `src/db.py` | Camada de banco dual-mode: SQLite local ou PostgreSQL em producao |
| `src/etl.py` | Parser da planilha, normalizacao, consolidacao e regras de calculo |
| `src/acerto_contas.py` | Regras automaticas de acerto de contas |
| `src/consolidado_component.py` | Tabela interativa do consolidado, semaforo e observacoes inline |
| `scripts/migrate_to_postgres.py` | Migracao do SQLite local para PostgreSQL |
| `data/app.db` | Banco local de trabalho, nao deve ser fonte oficial em producao |

## Banco de dados

Banco atual local:

```text
data/app.db
```

Banco temporario para validacao externa:

```text
PostgreSQL gerenciado no Render
```

Banco recomendado para producao definitiva:

```text
PostgreSQL
```

Se o Render estiver no plano Free, trate como ambiente de piloto/homologacao. A base definitiva deve ficar em plano com backup/persistencia adequada ou no banco corporativo da TI.

Tabelas mais importantes:

| Tabela | Uso |
|---|---|
| `base_dinamica` | Fonte principal consolidada por unidade e operadora |
| `faturamento` | Dados normalizados de faturamento |
| `contabilidade` | Dados normalizados de recebimentos |
| `de_para_unidades` | Padronizacao de unidades |
| `de_para_operadoras` | Padronizacao de operadoras |
| `visual_preferences` | Preferencias visuais do portal |
| `importacoes` | Historico de cargas |
| `exportacoes` | Historico de relatorios gerados |
| `inconsistencias_manuais` | Tratamentos manuais de auditoria |
| `metadata` | Controle tecnico e versao da base |

## Fluxo de migracao para banco corporativo

Quando a TI disponibilizar um banco corporativo PostgreSQL:

1. Criar usuario/schema para o portal.
2. Liberar conexao segura a partir do ambiente onde o app ira rodar.
3. Entregar a connection string no formato:

```text
postgresql://USUARIO:SENHA@HOST:PORTA/BANCO?sslmode=require
```

4. Rodar migracao a partir da base atual:

```powershell
python scripts/migrate_to_postgres.py --db data/app.db --pg-url "DATABASE_URL_DA_TI"
```

5. Configurar `DATABASE_URL` no ambiente definitivo.
6. Subir a aplicacao apontando para o novo banco.
7. Validar contagem de linhas e edicoes persistentes.

## Validacoes obrigatorias apos migracao

Antes de liberar para usuarios:

- Conferir se a tela `Consolidado` abre.
- Conferir se aparecem as 124 linhas analiticas esperadas na base atual.
- Alterar um semaforo em uma linha.
- Alterar uma observacao.
- Atualizar a pagina e confirmar que as alteracoes permaneceram.
- Conferir a aba `Acerto de contas`.
- Conferir importacao de nova planilha em ambiente homologacao.
- Conferir exportacao Excel.

## Seguranca

Situacao atual:

- `APP_PASSWORD` protege o acesso com senha simples.
- Credenciais nao ficam no Git.
- `data/app.db` foi removido do controle de versao.

Recomendacao para TI:

- Trocar `APP_PASSWORD` por autenticacao corporativa, como SSO, Azure AD, Google Workspace ou proxy autenticado.
- Colocar o app atras de rede/VPN corporativa, se necessario.
- Criar perfis de acesso: leitura, edicao e administracao.
- Criar trilha de auditoria para edicoes sensiveis.
- Definir politica de backup do PostgreSQL.

## Pontos que devem virar requisitos de TI

Quando o projeto sair da etapa temporaria:

- Ambiente de homologacao separado de producao.
- Banco PostgreSQL gerenciado pela TI.
- Backup automatico e restauracao testada.
- Controle de acesso por usuario nominal.
- Registro de quem alterou semaforo, observacao, DE/PARA e importacoes.
- Log de importacao com hash do arquivo e usuario.
- Processo formal para atualizar base mensal.
- Monitoramento do app e do banco.

## O que evitar

- Nao usar SQLite como banco oficial de varias pessoas.
- Nao colocar senha ou connection string no codigo.
- Nao versionar `.streamlit/secrets.toml`.
- Nao depender de alteracoes manuais direto no banco sem script ou registro.
- Nao dar deploy que sobrescreva dados operacionais do banco.

## Decisao importante ja tomada

`SYNC_CLOUD_SEED` deve ficar `0` em producao.

Isso evita que um deploy de codigo sobrescreva o banco usado pelos usuarios. Atualizacoes de base devem acontecer pelo portal ou por script controlado, nao automaticamente a cada publicacao.

## Pacote minimo para entregar a TI

Quando chegar a hora, enviar:

- Link do repositorio Git.
- Este documento.
- `docs/OPERACAO_MANUTENCAO_E_PASSAGEM_TI.md`.
- `docs/DEPLOY_PROFISSIONAL.md`.
- Lista de variaveis de ambiente.
- Backup/export do banco atual.
- Comando de migracao.
- Contatos responsaveis pelo processo de faturamento/recebimento.

## Documento operacional detalhado

O roteiro completo de operacao, manutencao, upgrades, incidentes, backup, manutencao de banco e passagem para TI esta em:

```text
docs/OPERACAO_MANUTENCAO_E_PASSAGEM_TI.md
```

Esse documento deve ser mantido atualizado sempre que houver mudanca relevante na arquitetura, no banco, no processo de deploy ou no fluxo mensal de carga.
