---
tipo: tecnologia
sistema: BigQuery
status: fonte_unica_verdade_analitica
ultima_revisao: 2026-08-12
---

# BigQuery

Fonte única de verdade analítica do AgroLog MT.

## Regras

- criar tabelas sob demanda;
- `data_referencia` é a preferência de particionamento quando compatível com o domínio;
- clustering pelas chaves reais de consulta;
- staging antes da camada final;
- MERGE ou append conforme contrato da fonte;
- cargas idempotentes;
- histórico preservado;
- raw fora do GitHub, preferencialmente no GCS;
- nenhuma IA recebe acesso irrestrito ao banco.

## Datas obrigatórias

`data_referencia`, `data_publicacao`, `data_coleta`, `competencia` quando aplicáveis.

## Acesso futuro

[[AgroLog Gateway]] deve expor consultas semânticas controladas para ChatGPT/OpenAI, Claude e demais consumidores autorizados.
