# Controle Executivo - Faturamento x Recebimento

## Objetivo

Aplicacao Streamlit para controle executivo de faturamento versus recebimento. O sistema importa bases financeiras, padroniza unidades e operadoras por DE/PARA, calcula o consolidado, identifica inconsistencias, permite comentarios manuais e gera relatorios executivos.

O foco visual e operacional e uma apresentacao para diretoria: telas limpas, indicadores objetivos, tabela consolidada responsiva e destaque claro para colunas de faturamento.

## Stack

- Python
- Streamlit
- Pandas
- SQLite
- OpenPyXL
- XlsxWriter

Arquivos principais:

- `app.py`: interface, filtros, telas, importacoes, editores e exportacoes.
- `src/etl.py`: leitura, limpeza, parser da aba `DINAMICA`, DE/PARA e consolidacao.
- `scripts/import_dinamica_base.py`: importacao direta da aba `DINAMICA` via terminal.
- `scripts/seed_database.py`: recria a base inicial quando `data/app.db` nao existe.
- `data/app.db`: banco SQLite usado pelo app local.
- `.streamlit/config.toml`: tema e configuracao base para deploy.
- `render.yaml`: blueprint para deploy em Render.

## Modelo De Dados

Tabelas principais no SQLite:

- `base_dinamica`: fonte principal quando a aba `DINAMICA` foi importada.
- `faturamento`: base normalizada de faturamento por unidade, operadora e mes.
- `contabilidade`: base normalizada de recebimentos por unidade, operadora e mes.
- `de_para_unidades`: padronizacao de nomes de unidades.
- `de_para_operadoras`: padronizacao de nomes de operadoras.
- `comentarios_manuais`: justificativas manuais por unidade, operadora, ano e mes.
- `importacoes`: historico de arquivos importados.
- `exportacoes`: historico de relatorios gerados.
- `inconsistencias_manuais`: tratamento operacional de inconsistencias.

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
- observacoes fiscais/manuais dentro da tabela;
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

As preferencias ficam registradas na tabela SQLite `visual_preferences`:

- ocultar/reexibir cards;
- ocultar/reexibir colunas;
- alterar ordem numerica das colunas;
- restaurar padrao.

Colunas `Unidade` e `Operadora` ficam sempre visiveis para preservar leitura executiva.

Na tela `Configuracoes`, o usuario precisa clicar em `Salvar preferencias de cards` ou `Salvar preferencias de colunas` para aplicar a configuracao nas abas principais.

Observacao sobre deploy gratuito: no Streamlit Community Cloud, alteracoes em SQLite local funcionam durante a vida da instancia, mas podem ser perdidas em reinicios/redeploys. Para persistencia definitiva entre usuarios e reinicios, migrar `visual_preferences`, comentarios e base operacional para um banco externo, como PostgreSQL/Supabase/Neon.

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
5. Publicar e compartilhar a URL com os usuarios autorizados.

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
