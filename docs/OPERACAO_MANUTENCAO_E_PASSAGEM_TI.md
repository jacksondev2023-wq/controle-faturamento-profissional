# Operacao, manutencao e passagem para TI

Este documento e o manual de continuidade do portal **Controle Executivo de Faturamento x Recebimento**. Ele deve ser usado para:

- manter o sistema rodando no Render durante a fase atual;
- orientar ajustes e upgrades do portal;
- orientar ajustes e upgrades do banco de dados;
- preparar a passagem futura para a TI corporativa;
- reduzir dependencia de conhecimento informal.

## 1. Estado atual do sistema

### Aplicacao

- Nome do servico no Render: `controle-faturamento-profissional`
- URL publica atual: `https://controle-faturamento-profissional.onrender.com`
- Repositorio GitHub: `jacksondev2023-wq/controle-faturamento-profissional`
- Branch de deploy: `main`
- Plataforma atual: Render Web Service
- Runtime: Python, fixado em `runtime.txt`
- Framework: Streamlit

### Banco de dados

- Banco local de desenvolvimento: `data/app.db` (SQLite)
- Banco compartilhado atual: PostgreSQL no Render
- Variavel que define o banco em producao: `DATABASE_URL`
- O banco compartilhado deve ser considerado a fonte oficial enquanto o portal estiver em uso por outras pessoas.

### Variaveis obrigatorias

No Render Web Service:

```text
DATABASE_URL=postgresql://...
APP_PASSWORD=senha-do-portal
SYNC_CLOUD_SEED=0
```

Regras:

- `DATABASE_URL` deve apontar para o PostgreSQL ativo.
- `APP_PASSWORD` habilita a tela de login.
- `SYNC_CLOUD_SEED` deve ficar `0` em producao para evitar sobrescrita do banco.
- Credenciais nunca devem ser salvas no GitHub, README, docs ou codigo.

## 2. Responsabilidades por camada

| Camada | Arquivos principais | Responsabilidade |
|---|---|---|
| Interface | `app.py` | Telas, filtros, login, navegacao, importacoes, exportacoes, visualizacoes |
| Banco | `src/db.py` | Escolher SQLite local ou PostgreSQL cloud, executar queries, criar colunas/tabelas |
| ETL | `src/etl.py` | Ler planilhas, normalizar colunas, padronizar unidades/operadoras, montar bases |
| Consolidado interativo | `src/consolidado_component.py` | Tabela executiva, farol, observacao inline |
| Acertos | `src/acerto_contas.py` | Regras automaticas de repasse entre filial de atendimento/fiscal |
| Migracao | `scripts/migrate_to_postgres.py` | Copiar banco SQLite para PostgreSQL e validar contagens |
| Seed local | `scripts/seed_database.py` | Recriar base local a partir dos arquivos brutos em desenvolvimento |
| Deploy | `render.yaml`, `runtime.txt`, `requirements.txt` | Configuracao do Render, Python e dependencias |

## 3. Tabelas do banco

### Tabelas operacionais

| Tabela | Funcao | Observacao de manutencao |
|---|---|---|
| `base_dinamica` | Base principal da tela Consolidado | Guarda farol (`sinal_diretoria`) e observacao editada |
| `faturamento` | Faturamento normalizado | Usada para analises e auditoria |
| `contabilidade` | Recebimentos normalizados | Usada para recebido bruto/liquido e observacoes fiscais |
| `consolidado_historico` | Historico consolidado por mes | Mantem meses antigos quando nao ha base bruta completa |
| `comentarios_manuais` | Comentarios por unidade/operadora/mes | Deve ser preservada em migracoes |
| `visual_preferences` | Preferencias visuais do portal | Deve ser preservada em deploys |
| `importacoes` | Historico de cargas | Importante para auditoria |
| `exportacoes` | Historico de exportacoes | Importante para auditoria e rastreio |
| `inconsistencias_manuais` | Tratamentos manuais de auditoria | Deve ser preservada |

### Tabelas de padronizacao

| Tabela | Funcao |
|---|---|
| `de_para_unidades` | DE/PARA de filiais/unidades |
| `de_para_operadoras` | DE/PARA de operadoras/convenios |

### Tabelas tecnicas e brutas

| Tabela | Funcao |
|---|---|
| `metadata` | Versao da base e metadados tecnicos |
| `raw_faturamento_upload` | Copia bruta do ultimo faturamento importado |
| `raw_contabilidade_upload` | Copia bruta da ultima contabilidade importada |

## 4. Campos sensiveis para negocio

Na tabela `base_dinamica`:

| Campo | Uso |
|---|---|
| `unidade_padrao` | Filial/unidade padronizada |
| `operadora_padrao` | Operadora/convenio padronizado |
| `faturado_marco`, `faturado_abril` | Valores faturados por mes |
| `rec_bruto_marco`, `rec_bruto_abril`, `rec_bruto_maio` | Recebimentos brutos |
| `rec_liquido_marco`, `rec_liquido_abril`, `rec_liquido_maio` | Recebimentos liquidos |
| `sinal_diretoria` | Farol: vazio, verde, amarelo ou vermelho |
| `alerta_diretoria` | Compatibilidade historica com vermelho |
| `observacao` | Observacao editavel da linha |
| `atualizado_em` | Data/hora da ultima atualizacao controlada |

Esses campos devem ser tratados como dados operacionais. Qualquer migracao ou importacao precisa preservar as edicoes de apresentacao quando for essa a intencao do processo.

## 5. Rotina operacional recomendada

### Diaria ou antes de apresentacoes

1. Abrir o portal.
2. Fazer login.
3. Conferir se a tela `Dashboard Executivo` abre.
4. Conferir se a tela `Consolidado` abre.
5. Alterar um farol de teste e retornar ao valor correto.
6. Atualizar a pagina e confirmar que a alteracao persistiu.
7. Conferir se a aba de acertos abre.

### Mensal, quando chegar nova planilha

1. Salvar uma copia do arquivo original em pasta controlada.
2. Fazer backup/exportacao do banco antes da importacao.
3. Importar em ambiente local ou homologacao, quando disponivel.
4. Conferir quantidade de linhas e totais principais.
5. Conferir se unidades e operadoras novas entraram no DE/PARA.
6. Conferir observacoes fiscais relevantes.
7. Validar consolidado com a area de negocio.
8. So depois liberar para uso da diretoria.

### Apos qualquer deploy

1. Abrir a URL publica.
2. Confirmar login.
3. Trocar de abas sem pedir senha novamente.
4. Confirmar botao `Sair`.
5. Conferir `Consolidado`.
6. Editar farol e observacao em uma linha controlada.
7. Atualizar a pagina e confirmar persistencia.
8. Conferir logs do Render por erros.

## 6. Processo de manutencao do codigo

### Fluxo padrao

1. Criar ou registrar a demanda.
2. Entender se a mudanca e visual, regra de negocio, banco ou infraestrutura.
3. Alterar o codigo localmente.
4. Rodar validacoes minimas:

```powershell
python -m py_compile app.py src\db.py src\etl.py src\acerto_contas.py src\consolidado_component.py scripts\migrate_to_postgres.py
```

5. Rodar localmente quando a mudanca afetar interface:

```powershell
streamlit run app.py
```

6. Validar visualmente.
7. Fazer commit.
8. Fazer push para `main`.
9. Acompanhar deploy no Render.
10. Executar checklist pos-deploy.

### Comandos de publicacao

```powershell
git status
git add .
git commit -m "Descrever alteracao"
git push origin main
```

Evitar commits que misturem muitas coisas diferentes. Mudancas de banco, layout e regra de negocio devem ser separadas quando possivel.

## 7. Processo de manutencao do banco

### Regra principal

Nunca fazer alteracao estrutural direto em producao sem:

- backup antes;
- entendimento do impacto;
- teste local ou em homologacao;
- registro no Git ou em documento de mudanca;
- validacao de leitura e gravacao depois.

### Alteracoes simples

Exemplos:

- adicionar uma coluna para nova classificacao;
- criar uma nova tabela de auditoria;
- incluir campo de usuario responsavel;
- criar tabela para modulo de glosas.

Processo recomendado:

1. Definir nome da tabela/coluna e tipo.
2. Atualizar `src/db.py` ou a rotina da tela para criar a estrutura quando necessario.
3. Atualizar scripts de migracao se a estrutura precisar ser copiada entre bancos.
4. Atualizar documentacao de tabelas.
5. Testar local.
6. Testar no banco cloud ou homologacao.
7. Fazer deploy.

### Alteracoes complexas

Exemplos:

- separar usuarios e permissoes;
- transformar farol/observacao em historico auditavel;
- criar modulo de glosas com varias tabelas;
- mudar a chave logica do consolidado;
- trocar provedor de banco.

Processo recomendado:

1. Desenhar o modelo antes de codar.
2. Criar plano de migracao e rollback.
3. Criar backup.
4. Criar scripts versionados de migracao.
5. Rodar em copia do banco.
6. Validar contagem, totais e telas.
7. Agendar janela de mudanca.
8. Aplicar em producao.
9. Rodar checklist pos-migracao.

## 8. Backup e recuperacao

### Enquanto estiver no Render Free

O banco Free deve ser tratado como piloto/homologacao. Antes de importacoes importantes ou reunioes criticas, gere copia dos dados.

Opcoes:

- exportar relatorios pelo proprio portal;
- usar ferramenta externa de PostgreSQL;
- usar `pg_dump`, se disponivel na maquina.

Exemplo com `pg_dump`:

```powershell
pg_dump --dbname "EXTERNAL_DATABASE_URL" --format=custom --file "backup_faturamento_YYYYMMDD.dump"
```

Exemplo de restauracao em outro banco:

```powershell
pg_restore --clean --if-exists --dbname "DATABASE_URL_DESTINO" "backup_faturamento_YYYYMMDD.dump"
```

Nao colocar `DATABASE_URL` real em arquivo versionado.

### Backup recomendado para producao definitiva

Quando estiver em ambiente da TI ou plano pago:

- backup automatico diario;
- retencao minima de 30 dias;
- teste mensal de restauracao;
- backup manual antes de grandes importacoes;
- separacao entre homologacao e producao.

## 9. Plano de upgrade

### Upgrade de dependencias Python

Arquivos envolvidos:

- `requirements.txt`
- `runtime.txt`

Processo:

1. Atualizar versoes em ambiente local.
2. Rodar `pip install -r requirements.txt`.
3. Rodar `python -m py_compile ...`.
4. Abrir Streamlit local.
5. Conferir login, navegacao, consolidado, importacao e exportacao.
6. Fazer deploy.
7. Conferir logs do Render.

Frequencia sugerida:

- revisao trimestral;
- revisao imediata se houver alerta de seguranca.

### Upgrade de Python

Hoje o projeto usa `runtime.txt`.

Processo:

1. Escolher versao suportada pelo Render e pelas bibliotecas.
2. Alterar `runtime.txt`.
3. Testar instalacao local ou em branch.
4. Fazer deploy em horario de menor uso.
5. Conferir logs.

Evitar versoes muito novas sem validacao, porque bibliotecas como pandas, numpy e psycopg2 podem demorar a suportar releases recentes.

### Upgrade do banco

Processo:

1. Fazer backup.
2. Verificar compatibilidade do PostgreSQL.
3. Subir ambiente de teste ou restaurar backup em banco temporario.
4. Apontar `DATABASE_URL` de homologacao para esse banco.
5. Validar app.
6. Executar upgrade em producao.
7. Validar app novamente.

## 10. Plano de passagem para TI

### Fase 1 - Organizacao atual

Status esperado:

- GitHub atualizado;
- Render funcionando;
- PostgreSQL compartilhado ativo;
- login simples por `APP_PASSWORD`;
- documentacao tecnica atualizada.

Entregaveis:

- URL do portal;
- URL do repositorio;
- documentos em `docs/`;
- lista de variaveis de ambiente;
- responsavel de negocio;
- responsavel tecnico atual.

### Fase 2 - Homologacao com TI

Objetivo:

Fazer a TI entender o sistema sem alterar producao.

Atividades:

- criar ambiente de homologacao;
- restaurar copia do banco;
- rodar portal apontando para banco de homologacao;
- testar carga de planilha;
- validar login e permissoes;
- revisar requisitos de seguranca.

### Fase 3 - Banco corporativo

Objetivo:

Mover a fonte oficial para banco gerenciado pela TI.

Atividades:

1. TI cria banco PostgreSQL ou schema dedicado.
2. TI cria usuario de aplicacao com permissoes minimas.
3. TI libera conexao a partir do ambiente do app.
4. Exportar banco atual.
5. Restaurar ou migrar para banco corporativo.
6. Atualizar `DATABASE_URL`.
7. Rodar validacoes obrigatorias.
8. Congelar banco antigo como backup temporario.

### Fase 4 - Aplicacao corporativa

Objetivo:

Substituir a etapa Render/piloto por ambiente definitivo.

Opcoes:

- manter Render com plano adequado e governanca;
- migrar para servidor interno;
- migrar para container corporativo;
- migrar para plataforma cloud da empresa.

Pontos obrigatorios:

- variaveis de ambiente seguras;
- autentificacao corporativa;
- backups;
- logs;
- monitoramento;
- processo de deploy controlado.

### Fase 5 - Evolucao funcional

Possiveis proximos modulos:

- glosas em formato executivo;
- trilha de auditoria por usuario;
- perfis de acesso;
- historico de farol e observacao;
- consolidado mensal comparativo;
- exportacao PDF para diretoria;
- conciliacao automatica mais detalhada;
- integracao futura com sistemas internos.

## 11. Requisitos que devem ser passados para TI

### Infraestrutura

- ambiente de homologacao;
- ambiente de producao;
- banco PostgreSQL gerenciado;
- backup automatico;
- monitoramento de aplicacao;
- monitoramento de banco;
- processo de deploy;
- armazenamento seguro de variaveis.

### Seguranca

- autenticacao nominal por usuario;
- controle de perfil;
- log de acesso;
- log de edicoes;
- politica de senha ou SSO;
- segregacao entre leitura, edicao e administracao;
- criptografia em transito;
- backup com acesso restrito.

### Dados

- dicionario de tabelas;
- processo de importacao mensal;
- processo de ajuste de DE/PARA;
- processo de correcao de observacoes;
- regra de acerto de contas;
- regra de consolidado;
- regra de glosas quando o modulo for criado.

## 12. Plano de manutencao recorrente

| Frequencia | Atividade | Responsavel sugerido |
|---|---|---|
| Diario/antes de reuniao | Abrir portal, testar login e telas criticas | Area de negocio |
| Semanal | Conferir logs do Render e uso do banco | Responsavel tecnico |
| Mensal | Importar nova base e validar totais | Area de negocio + tecnico |
| Mensal | Fazer backup antes da carga | Responsavel tecnico |
| Trimestral | Revisar dependencias e runtime | Responsavel tecnico/TI |
| Trimestral | Revisar acessos e senha | Responsavel de negocio/TI |
| Semestral | Testar restauracao de backup | TI |
| Anual | Revisar arquitetura e custos | Gestao + TI |

## 13. Plano de incidentes

### Portal fora do ar

1. Verificar status do Render.
2. Verificar ultimo deploy.
3. Verificar logs.
4. Se erro veio de deploy recente, fazer rollback para deploy anterior.
5. Se erro e banco, testar conexao PostgreSQL.
6. Registrar causa e acao tomada.

### Login nao aparece

1. Conferir se `APP_PASSWORD` existe no Environment do Web Service.
2. Conferir se o deploy mais recente esta live.
3. Limpar cache do navegador.
4. Conferir logs do app.

### Dados nao salvam

1. Conferir `DATABASE_URL`.
2. Testar se o app esta em PostgreSQL e nao SQLite temporario.
3. Conferir permissoes do usuario do banco.
4. Conferir logs da query.
5. Fazer backup antes de qualquer tentativa de correcao manual.

### Importacao gerou dados errados

1. Nao fazer novo deploy para tentar corrigir no susto.
2. Exportar estado atual para evidencia.
3. Restaurar backup anterior ou reprocessar base correta em ambiente controlado.
4. Validar totais.
5. Registrar arquivo usado, data e responsavel.

## 14. Controle de mudancas

Toda mudanca relevante deve registrar:

- data;
- objetivo;
- arquivos alterados;
- impacto esperado;
- teste realizado;
- se mexeu no banco;
- se exigiu backup;
- responsavel pela validacao.

Sugestao de formato para commit:

```text
Area: resumo curto da mudanca
```

Exemplos:

```text
Consolidado: ajustar edicao inline de observacoes
Banco: incluir tabela de auditoria de farol
Deploy: atualizar runtime Python
Glosas: criar visao executiva inicial
```

## 15. Pontos de atencao ja conhecidos

- O banco Render Free e temporario para piloto; nao deve ser unico ponto de producao definitiva.
- A senha atual do portal e simples (`APP_PASSWORD`); para TI, trocar por autenticacao corporativa.
- A URL do banco ja foi manipulada durante configuracao; se houver risco de exposicao, rotacionar a senha do banco no Render.
- `SYNC_CLOUD_SEED` deve permanecer `0` em producao.
- O arquivo `data/app.db` nao deve voltar para o Git.
- Alteracoes manuais diretas no banco devem ser excecao, nao rotina.

## 16. Pacote final para entrega

Quando for entregar para TI, incluir:

- link do repositorio GitHub;
- link do portal atual;
- backup/export do banco atual;
- lista de variaveis de ambiente sem valores sensiveis;
- este documento;
- `docs/TRANSICAO_TI.md`;
- `docs/DEPLOY_PROFISSIONAL.md`;
- `docs/PROJETO_CONTROLE_FATURAMENTO.md`;
- contato do responsavel de negocio;
- contato do responsavel tecnico;
- lista de proximas demandas priorizadas.
