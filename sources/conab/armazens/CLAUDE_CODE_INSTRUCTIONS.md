# Claude Code — CONAB Armazéns

Objetivo: implantar a carga real ponta a ponta no Google Cloud sem reinterpretar a regra de negócio.

## Contratos obrigatórios

- Ler `source_manifest.yaml` e `schema.json` antes de alterar código.
- Preservar arquivo bruto no GCS com hash e timestamp de coleta.
- Nunca apagar unidade apenas porque não apareceu no snapshot atual.
- Tratar ausência como `ausente_no_snapshot_atual`.
- Carregar staging antes de qualquer MERGE.
- Reexecução do mesmo arquivo deve ser idempotente.
- Manter `data_referencia`, `data_publicacao`, `data_coleta` e `competencia`.
- Classificar a evidência como `OBSERVADO`.
- Não mudar nomes/semântica sem registrar migração.

## Ordem de execução

1. baixar/receber arquivo oficial;
2. calcular SHA-256;
3. gravar raw no GCS;
4. criar `snapshot_id` e `ingestion_run_id`;
5. normalizar cabeçalhos/encoding/unidades;
6. validar schema e regras de qualidade;
7. carregar `logistica.stg_armazens`;
8. calcular chave natural e comparar com snapshot anterior;
9. registrar métricas de movimento;
10. executar MERGE em `logistica.armazens`;
11. registrar `armazens_snapshots` e membros;
12. executar DQ pós-carga;
13. testar consulta de última versão válida;
14. reexecutar o mesmo arquivo e comprovar ausência de duplicação.

## Critério de aceite

Só marcar `INTEGRADA/PRODUCAO` quando houver evidência da carga real no BigQuery, logs, snapshot, DQ e teste idempotente. Código local ou dry-run não concluem a tarefa.
