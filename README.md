# Controle Executivo de Faturamento x Recebimento

Projeto web em **Streamlit + PostgreSQL** para transformar o relatorio manual de faturamento vs. recebimento em uma ferramenta profissional, atualizavel por upload, com banco persistente para uso por outras pessoas e preparada para futura transicao para a TI.

Em desenvolvimento local, o projeto tambem funciona com SQLite em `data/app.db`.

## Objetivo

Manter a mesma visao executiva que a diretoria ja entende, mas tirando o processo do modo manual/amador.

A aplicacao permite:

- usar os arquivos reais ja enviados como base inicial;
- carregar novos faturamentos por upload;
- carregar novas bases da contabilidade por upload;
- escolher mes(es) de faturamento;
- escolher mes(es) de recebimento;
- manter DE/PARA editavel de unidades e operadoras;
- gerar dashboard executivo;
- visualizar pendencias;
- marcar farol de diretoria por linha;
- editar observacoes diretamente no consolidado;
- gerar visao de acerto de contas;
- exportar Excel profissional;
- separar comentarios manuais dos comentarios fiscais.

## Estrutura do projeto

```text
controle-faturamento-profissional/
|-- app.py
|-- requirements.txt
|-- runtime.txt
|-- render.yaml
|-- data/
|   |-- app.db
|   |-- raw/
|   `-- processed/
|-- scripts/
|   |-- seed_database.py
|   |-- import_dinamica_base.py
|   `-- migrate_to_postgres.py
|-- src/
|   |-- db.py
|   |-- etl.py
|   |-- acerto_contas.py
|   `-- consolidado_component.py
`-- docs/
```

## Como rodar localmente

Dentro da pasta do projeto:

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Para recriar a base SQLite local a partir dos arquivos de seed:

```powershell
python scripts/seed_database.py
```

## Deploy profissional

Para uso por outras pessoas, nao dependa do SQLite local. Publique o app no Render/GitHub com PostgreSQL persistente configurado em `DATABASE_URL` e senha de acesso em `APP_PASSWORD`.

O passo a passo esta em:

```text
docs/DEPLOY_PROFISSIONAL.md
```

Para uma futura transicao para infraestrutura da TI, use:

```text
docs/TRANSICAO_TI.md
```

Para operacao continua, manutencoes, upgrades e plano detalhado de passagem para TI, use:

```text
docs/OPERACAO_MANUTENCAO_E_PASSAGEM_TI.md
```

## Documentacao tecnica

A documentacao completa do estado atual do projeto, incluindo fluxo de dados, importacao da aba `DINAMICA`, preferencias de visualizacao e deploy, esta em:

```text
docs/PROJETO_CONTROLE_FATURAMENTO.md
```

## Base inicial

A base inicial usa os arquivos enviados no processo de construcao:

- faturamento de Abril/2026;
- contabilidade de Abril e Maio/2026;
- relatorio historico Marco/Abril;
- relatorio atual Abril/Maio;
- prompt original do processo.

## Observacao importante sobre marco

O mes de marco esta incluido como historico consolidado a partir do modelo antigo.

Para uma analise totalmente rastreavel de marco, com nota, atendimento, paciente, operadora e recebimento bruto/liquido, sera necessario importar os arquivos brutos de:

- faturamento de marco;
- contabilidade de marco.

## Proximos passos recomendados

1. Formalizar ambiente de homologacao separado da producao.
2. Criar autenticacao nominal por usuario ou SSO corporativo.
3. Criar trilha de auditoria para farol, observacoes, DE/PARA e importacoes.
4. Estruturar modulo executivo de glosas.
5. Migrar banco para plano com backup/persistencia adequada ou infraestrutura da TI.
6. Criar processo mensal formal de carga, validacao e backup.
7. Criar exportacao PDF para diretoria.
