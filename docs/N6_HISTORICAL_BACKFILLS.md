# N6 — Backfills Históricos

## Princípio temporal

Backfill não pode fingir que o AgroLog coletou um arquivo no passado. `data_coleta` sempre registra quando o sistema realmente obteve o artefato.

Para reconstruir o conjunto informacional histórico existe uma segunda noção explícita: `data_disponibilidade`. Ela só pode antecipar `data_coleta` quando `availability_verified=true` e houver evidência documental de que o artefato já estava publicamente disponível naquele momento.

`models/point_in_time.available_at` aplica:

- regra normal: `max(data_publicacao, data_coleta)`;
- backfill histórico verificado: `data_disponibilidade` quando `availability_verified=true`.

A exceção é fail-closed: uma data antiga informada sem flag verificada não altera o cutoff.

## CONAB Safra

`scripts/backfill_conab_safra.py` descobre levantamentos no GOV.BR, extrai o timestamp original de publicação da página e bloqueia qualquer item para o qual essa evidência não possa ser determinada.

Execução recomendada primeiro em dry-run:

```bash
PYTHONPATH=. python scripts/backfill_conab_safra.py --safra 2025/26 --dry-run
```

Na execução real:

1. baixa o XLSX oficial;
2. calcula SHA-256;
3. preserva RAW no Drive;
4. mantém `data_coleta` real;
5. grava `data_publicacao`/`data_disponibilidade` da página oficial;
6. executa parser e quality gates;
7. carrega `agro.conab_safra_graos` de forma idempotente;
8. grava manifesto/auditoria.

## Comex Stat

`scripts/backfill_comexstat.py` trabalha arquivo anual por variante em streaming. O namespace físico canônico é `comercio_exterior`, alinhado a `contracts/comexstat.v1.json` e ao loader.

```bash
PYTHONPATH=. python scripts/backfill_comexstat.py --start-year 1997 --end-year 2026 --variant ncm_export --dry-run
```

Na execução real o download mantém TLS verificado, grava RAW por arquivo, normaliza CSV para NDJSON em streaming e faz load job + MERGE idempotente.

O `Last-Modified` HTTP é preservado, mas não é tratado automaticamente como prova da disponibilidade original de cada competência mensal. Por isso os backfills Comex permanecem `availability_verified=false` até uma regra oficial de calendário/vintage ser validada.

## Namespaces físicos confirmados

- CONAB Safra: `agro.conab_safra_graos`;
- Comex Stat: `comercio_exterior.comexstat_*`;
- CONAB Armazéns: `logistica.armazens_conab`;
- referência municipal: `referencia.municipios_ibge`.

O contrato do Data Mart deve apontar para esses nomes e não criar aliases concorrentes apenas por conveniência.
