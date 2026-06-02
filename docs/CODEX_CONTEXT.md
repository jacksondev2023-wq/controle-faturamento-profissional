
# Contexto para continuar este projeto no Codex

Você está trabalhando em uma aplicação interna para controle executivo de **Faturamento x Recebimento** de uma empresa de home care/hospitalar.

## Objetivo do sistema

Substituir um relatório Excel manual por uma interface web profissional, mantendo a mesma lógica visual que a diretoria já acompanha, porém com atualização fácil via upload.

A ferramenta deve permitir:

1. Upload de faturamento IW.
2. Upload de contabilidade/recebimentos.
3. Seleção dinâmica de:
   - mês(es) de faturamento;
   - mês(es) de recebimento;
   - unidade/filial;
   - operadora.
4. Padronização via DE/PARA de unidades e operadoras.
5. Dashboard executivo.
6. Exportação para Excel.
7. Controle de comentários.
8. Tela de inconsistências.

## Regras de negócio principais

### Faturamento

Arquivo típico: `faturamento_abril_2026.xlsx`.

Colunas comuns:

- UNIDADE
- CONVENIO ou CONVENIO CONSOLIDADO
- Valor a Cobrar
- COMPETENCIA FAT ou Vigência de:
- ID Doc
- Nome do Paciente

O faturamento deve ser agrupado por:

- unidade_padrao
- operadora_padrao

### Contabilidade

Arquivo típico: `contabilidade_abril_maio_2026.xlsx`.

Colunas comuns:

- Nº NF
- UNIDADE
- OPERADORA
- VALOR BRUTO
- DTA DE PAGO
- VALOR LÍQUIDO
- OBSERVAÇÕES
- MÊS DE RECEBIMENTO

Os recebimentos devem ser agrupados por:

- unidade_padrao
- operadora_padrao
- mês de recebimento

### Comentários

Regra pedida pelo usuário:

- manter automaticamente apenas comentários que informem que o recebimento aconteceu em **filial fiscal diferente**;
- remover/deixar em branco os demais comentários, pois o usuário irá preencher manualmente.

O campo atual para isso é `observacao_fiscal`.

### Março

Existe um relatório consolidado antigo com Março/Abril, mas os arquivos brutos de faturamento e contabilidade de março ainda não estão disponíveis neste projeto.

Portanto:

- março pode aparecer como histórico consolidado;
- para rastreabilidade completa, criar fluxo para importar o faturamento bruto e a contabilidade bruta de março quando forem enviados.

## Estrutura técnica atual

- `app.py`: interface Streamlit.
- `src/etl.py`: limpeza, normalização, DE/PARA de unidades/operadoras, consolidação.
- `scripts/seed_database.py`: cria `data/app.db` com os arquivos iniciais.
- `data/raw/`: arquivos reais usados como base inicial.
- `data/app.db`: SQLite inicial.

## Melhorias prioritárias

1. Deixar o dashboard com aparência mais corporativa:
   - sidebar mais limpa;
   - cards mais bonitos;
   - tabela executiva parecida com o Excel original;
   - cores discretas e profissionais.

2. Criar módulo de comentários:
   - comentário fiscal automático;
   - comentário manual por unidade/operadora/mês;
   - salvar comentário na tabela `comentarios_manuais`.

3. Melhorar importação:
   - registrar cada upload em uma tabela `importacoes`;
   - impedir duplicidade;
   - permitir limpar/reprocessar um mês.

4. Criar relatório por competência:
   - Fat Março x Rec Março;
   - Fat Março x Rec Março/Abril/Maio;
   - Fat Abril x Rec Abril/Maio;
   - Fat Março+Abril x Rec selecionados.

5. Futuramente migrar de SQLite para PostgreSQL.

## Comandos

```bash
pip install -r requirements.txt
python scripts/seed_database.py
streamlit run app.py
```

## Observação de produto

O usuário não quer apenas uma planilha bonita. Ele quer algo profissional, fácil de atualizar e que possa ser mostrado para diretoria com segurança.
