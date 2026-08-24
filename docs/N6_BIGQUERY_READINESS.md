# N6 — Inspeção de Readiness no BigQuery

## Objetivo

Substituir conferência manual por uma inspeção reproduzível do estado real das tabelas canônicas necessárias ao Data Mart Soja MT.

`scripts/inspect_n6_bigquery_readiness.py` é somente leitura. Ele:

1. carrega `contracts/soy_mt_datamart.v1.json`;
2. identifica todas as tabelas requeridas/alternativas;
3. verifica existência e schema;
4. lê número de linhas;
5. infere somente capacidades estruturais de point-in-time e geografia;
6. mede intervalo temporal, safras e snapshots quando os campos existem;
7. combina essas evidências com QA previamente homologado;
8. executa `evaluate_datamart`;
9. grava um JSON de evidência.

## QA não é inferido

A presença de uma tabela ou de colunas corretas não significa que o conteúdo passou QA. Por isso o inspector nunca transforma existência em `qa_status=pass`.

QA aprovado deve vir de um arquivo explícito `table -> pass/fail/unknown` produzido pelos validadores de cada fonte durante a homologação real. Na ausência dessa evidência o status permanece `unknown` e o Data Mart não é liberado.

## Execução

```bash
python scripts/inspect_n6_bigquery_readiness.py \
  --project <PROJECT_ID> \
  --qa-evidence outputs/n6-core/qa_evidence.json \
  --out outputs/n6-core/datamart_readiness.json
```

O exit code é 0 somente quando o gate do Data Mart passa; gate incompleto retorna código não-zero sem fazer escrita no BigQuery.

## Regra de segurança

O inspector não cria dataset, tabela, view, schema, IAM, job de carga ou artefato RAW. Consultas são apenas de agregação sobre tabelas existentes e nomes de dataset/tabela passam por validação de identificador.
