
# Controle Executivo de Faturamento x Recebimento

Projeto web em **Streamlit + SQLite** para transformar o relatório manual de faturamento vs. recebimento em uma ferramenta profissional, atualizável por upload e preparada para evoluir no Codex/VS Code.

## Objetivo

Manter a mesma visão executiva que a diretoria já entende, mas tirando o processo do modo manual/amador.

A aplicação permite:

- usar os arquivos reais já enviados como base inicial;
- carregar novos faturamentos por upload;
- carregar novas bases da contabilidade por upload;
- escolher mês(es) de faturamento;
- escolher mês(es) de recebimento;
- manter DE/PARA editável de unidades e operadoras;
- gerar dashboard executivo;
- visualizar pendências;
- exportar Excel profissional;
- separar comentários manuais dos comentários fiscais.

## Estrutura do projeto

```text
controle_faturamento_profissional/
├── app.py
├── requirements.txt
├── data/
│   ├── app.db
│   ├── raw/
│   │   ├── faturamento_abril_2026.xlsx
│   │   ├── contabilidade_abril_maio_2026.xlsx
│   │   ├── modelo_historico_fat_mar_rec_mar_abr.xlsx
│   │   ├── relatorio_atual_fat_abr_rec_abr_mai.xlsx
│   │   └── prompt_original.txt
│   └── processed/
├── scripts/
│   └── seed_database.py
├── src/
│   └── etl.py
└── docs/
    └── CODEX_CONTEXT.md
```

## Como rodar

Dentro da pasta do projeto:

```bash
pip install -r requirements.txt
python scripts/seed_database.py
streamlit run app.py
```

## Deploy profissional

Para uso por outras pessoas, nao dependa do SQLite local. Publique o app no Render/GitHub com PostgreSQL persistente configurado em `DATABASE_URL` e senha de acesso em `APP_PASSWORD`.

O passo a passo esta em:

```text
docs/DEPLOY_PROFISSIONAL.md
```

## Documentação técnica atualizada

A documentação completa do estado atual do projeto, incluindo fluxo de dados, importação da aba `DINAMICA`, preferências de visualização e deploy, está em:

```text
docs/PROJETO_CONTROLE_FATURAMENTO.md
```

## Base inicial

A base inicial já usa os arquivos enviados:

- Faturamento de Abril/2026;
- Contabilidade de Abril e Maio/2026;
- Relatório histórico Março/Abril;
- Relatório atual Abril/Maio;
- Prompt original do processo.

## Observação importante sobre março

O mês de março está incluído como **histórico consolidado** a partir do modelo antigo.

Para uma análise totalmente rastreável de março, com nota, atendimento, paciente, operadora e recebimento bruto/líquido, será necessário importar os arquivos brutos de:

- faturamento de março;
- contabilidade de março.

## Próximos passos recomendados

1. Melhorar layout visual do dashboard.
2. Criar tela de comentários manuais por filial/operadora.
3. Criar autenticação de usuários.
4. Migrar SQLite para PostgreSQL.
5. Criar histórico mensal definitivo.
6. Criar exportação PDF para diretoria.
7. Criar logs de importação e validação.
