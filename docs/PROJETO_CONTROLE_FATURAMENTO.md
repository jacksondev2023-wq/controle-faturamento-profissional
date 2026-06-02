# Controle Executivo - Faturamento x Recebimento

## Objetivo

Aplicacao Streamlit para controle executivo de faturamento versus recebimento. O sistema importa bases financeiras, padroniza unidades e operadoras por DE/PARA, calcula o consolidado, identifica inconsistencias, permite comentarios manuais e gera relatorios executivos.

O foco visual e operacional e uma apresentacao para diretoria: telas limpas, indicadores objetivos, tabela consolidada responsiva e destaque claro para colunas de faturamento.

## Stack

- Python
- Streamlit
- Pandas
- SQLite local
- PostgreSQL/Neon em producao
- SQLAlchemy
- OpenPyXL
- XlsxWriter

Arquivos principais:

- `app.py`: interface, filtros, telas, importacoes, editores e exportacoes.
- `src/etl.py`: leitura, limpeza, parser da aba `DINAMICA`, DE/PARA e consolidacao.
- `scripts/import_dinamica_base.py`: importacao direta da aba `DINAMICA` via terminal.
- `scripts/seed_database.py`: recria a base inicial quando `data/app.db` nao existe.
- `src/db.py`: camada de banco dual-mode, usando SQLite local e PostgreSQL no Streamlit Cloud.
- `data/app.db`: banco SQLite local e seed versionado para sincronizacao inicial/atualizacao operacional no cloud.
- `.streamlit/config.toml`: tema e configuracao base para deploy.
- `render.yaml`: blueprint para deploy em Render.

## Modelo De Dados

Tabelas principais no banco ativo (SQLite local ou PostgreSQL em producao):

- `base_dinamica`: fonte principal consolidada por unidade e operadora. Pode ser alimentada pela aba `DINAMICA` ou por uma base consolidada validada.
- `faturamento`: base normalizada de faturamento por unidade, operadora e mes.
- `contabilidade`: base normalizada de recebimentos por unidade, operadora e mes.
- `de_para_unidades`: padronizacao de nomes de unidades.
- `de_para_operadoras`: padronizacao de nomes de operadoras.
- `comentarios_manuais`: justificativas manuais por unidade, operadora, ano e mes.
- `importacoes`: historico de arquivos importados.
- `exportacoes`: historico de relatorios gerados.
- `inconsistencias_manuais`: tratamento operacional de inconsistencias.
- `visual_preferences`: preferencias persistidas de cards e colunas.
- `metadata`: metadados de versao da base e contexto tecnico.

Em producao, o app detecta `[connections.postgresql]` em `st.secrets` e usa PostgreSQL automaticamente. Sem secrets, usa `data/app.db`.

## Importacao Da Aba DINAMICA

O arquivo atualizado deve ser importado considerando apenas a aba `DINAMICA`.

Colunas reconhecidas pelo parser:

- `faturado_marco`
- `faturado_abril`
- `rec_bruto_marco`
- `rec_liquido_marco`
- `rec_bruto_abril`
- `rec_liquido_abril`
- `rec_bruto_maio`
- `rec_liquido_maio`
- `observacao`

Os totais da planilha nao sao usados. O sistema recalcula totais, diferencas e percentuais a partir das linhas de unidade e operadora.

### Base validada em 02/06/2026

Arquivo usado: `RELATORIO_FAT_ABR_REC_ABR_MAI 01-06-26 (1).xlsx`, aba `DINAMICA`.

Validacao aplicada:

- 120 pares de unidade/operadora importados da planilha para `base_dinamica`.
- A base anterior foi substituida; nomes de unidades, operadoras, valores e observacoes seguem a aba `DINAMICA`.
- `faturado_marco`: R$ 2.245.027,70.
- `faturado_abril`: R$ 19.791.682,33.
- `rec_bruto_abril`: R$ 20.914.898,01.
- `rec_liquido_abril`: R$ 20.013.112,58.
- `rec_bruto_maio`: R$ 15.454.014,26.
- `rec_liquido_maio`: R$ 14.349.406,00.
- 32 observacoes da planilha confirmadas na base.
- O padrao visual usa faturamento Marco/Abril e recebimentos Abril/Maio. Recebimento de marco nao aparece por padrao porque a aba `DINAMICA` atual nao possui valores recebidos nesse mes.

O marcador `metadata.base_seed_version` controla a sincronizacao da base operacional com o PostgreSQL no deploy.

Exemplo de importacao complementar via terminal:

```powershell
python scripts/import_dinamica_base.py "c:\caminho\arquivo.xlsx" --year 2026 --mode merge --columns "faturado_marco,rec_bruto_marco,rec_liquido_marco,rec_bruto_abril,rec_liquido_abril,observacao"
```

Exemplo substituindo toda a base:

```powershell
python scripts/import_dinamica_base.py "c:\caminho\arquivo.xlsx" --year 2026 --mode replace
```

## Regras De Consolidacao

O consolidado e calculado em `src/etl.py`, funcao `build_consolidado`.

Regras principais:

- Faturamento pode ter multiplos meses selecionados.
- Recebimento pode ter multiplos meses selecionados.
- Cada mes de faturamento gera uma coluna `fat_<mes>`, como `fat_3` e `fat_4`.
- `faturado` e a soma das colunas mensais de faturamento selecionadas.
- `total_recebido_bruto` e soma dos recebimentos brutos selecionados.
- `total_recebido_liquido` e soma dos recebimentos liquidos selecionados.
- `diferenca_pendente = faturado - total_recebido_bruto`.
- `% recebido = total_recebido_bruto / faturado`.

## Telas

### Dashboard Executivo

Mostra KPIs, grafico de recebimento por mes, top pendencias por unidade e tabela detalhada.

Cards podem ser ocultados/reexibidos em:

`Configuracoes > Preferencias de visualizacao > Dashboard Executivo`

Colunas da tabela detalhada tambem podem ser ocultadas, reexibidas e reordenadas nessa mesma area.

### Consolidado

Tela de apresentacao analitica por unidade e operadora. A tabela funciona como uma visao dinamica:

- subtotal por unidade;
- detalhe por operadora;
- observacoes fiscais/manuais em linhas de detalhe abaixo da respectiva operadora, com prefixo do nome da operadora e sem coluna horizontal de observacoes;
- subtotal por unidade apenas com valores financeiros; nao exibir resumo/total de observacoes abaixo da unidade;
- destaque visual nas colunas de faturamento;
- rolagem horizontal controlada para muitas colunas.

Cards e colunas sao configurados em:

`Configuracoes > Preferencias de visualizacao > Consolidado`

### Importacoes

Permite importar:

- base `DINAMICA`;
- faturamento IW;
- contabilidade/recebimentos.

Para a base `DINAMICA`, o usuario pode complementar ou substituir a base atual e escolher quais colunas entram no sistema.

### DE/PARA

Gerencia mapeamentos de nomes de unidades e operadoras.

### Comentarios

Permite editar comentarios manuais por unidade, operadora e competencia. Observacoes fiscais importadas ficam separadas dos comentarios manuais.

### Inconsistencias

Mostra auditoria operacional e permite tratamento das inconsistencias identificadas.

### Exportacoes

Gera relatorios em Excel e mantem historico de exportacoes. PDF esta previsto para etapa futura.

### Configuracoes

Central tecnica do sistema:

- preferencias de visualizacao;
- edicao manual da `base_dinamica`;
- consulta de bases carregadas;
- contexto tecnico.

## Preferencias De Visualizacao

As abas de apresentacao nao exibem controles de configuracao. A configuracao fica separada em `Configuracoes`.

As preferencias ficam registradas na tabela `visual_preferences` do banco ativo:

- ocultar/reexibir cards;
- ocultar/reexibir colunas;
- alterar ordem numerica das colunas;
- restaurar padrao.

Colunas `Unidade` e `Operadora` ficam sempre visiveis para preservar leitura executiva.

Na tela `Configuracoes`, o usuario precisa clicar em `Salvar preferencias de cards` ou `Salvar preferencias de colunas` para aplicar a configuracao nas abas principais.

No Streamlit Community Cloud, essas preferencias ficam persistidas no PostgreSQL/Neon e permanecem apos reinicios/redeploys. A leitura de preferencias nao usa cache, e a gravacao usa UPSERT para evitar perda entre usuarios.

## Cuidados Com Dados Sensíveis

Este projeto contem dados financeiros e nomes de unidades/operadoras. Para publicar:

- preferir repositorio privado;
- evitar subir planilhas brutas se nao forem necessarias;
- evitar publicar `data/app.db` em repositorio publico se ele contiver dados reais;
- restringir acesso ao app em ambiente corporativo;
- revisar backups em `data/backups` antes de qualquer deploy.

## Rodando Localmente

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Acesse:

```text
http://localhost:8501
```

## Deploy Recomendado

### Streamlit Community Cloud

E o caminho mais direto para este projeto, porque executa apps Streamlit a partir de um repositorio GitHub com `requirements.txt` e arquivo de entrada `app.py`.

Passos:

1. Subir o projeto para um repositorio GitHub, preferencialmente privado.
2. Acessar `https://share.streamlit.io`.
3. Criar app apontando para o repositorio, branch e arquivo `app.py`.
4. Selecionar a versao de Python nas configuracoes avancadas, se necessario.
5. Configurar o secret `[connections.postgresql]` com `connection_url` do Neon.
6. Publicar e compartilhar a URL com os usuarios autorizados.

Exemplo seguro de secrets:

```toml
[connections.postgresql]
connection_url = "postgresql://USER:PASSWORD@HOST/neondb?sslmode=require"
```

Nao versionar credenciais reais. O arquivo `.streamlit/secrets.toml` local deve permanecer no `.gitignore`.

Documentacao oficial:

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization

### Render

O arquivo `render.yaml` ja foi adicionado ao projeto. Ele inicia o app com:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

### Vercel

Vercel e excelente para frontends e funcoes serverless. Para este app Streamlit, nao e o alvo ideal porque o runtime Python da Vercel trabalha como Function HTTP, enquanto Streamlit precisa manter um servidor web ativo.

Documentacao oficial da Vercel sobre Python Functions:

- https://vercel.com/docs/functions/runtimes/python

Para usar Vercel de verdade, o caminho mais correto seria reescrever a interface em Next.js/React e transformar o backend em API separada. Para o estado atual do projeto, Streamlit Community Cloud ou Render sao mais adequados.

## Validacoes Executadas

Comandos usados para validacao:

```powershell
python -m compileall app.py src scripts
```

Tambem foram testadas as paginas principais com `streamlit.testing`:

- Dashboard Executivo
- Consolidado
- Importacoes
- Configuracoes
- Comentarios
- Inconsistencias
- Exportacoes

Pontos visuais verificados:

- Consolidado sem painel de configuracao na tela de apresentacao.
- Preferencias separadas em Configuracoes.
- Tabela consolidada sem fragmentos de HTML.
- Rolagem horizontal da tabela funcionando.
- Menu lateral compacto funcionando.
