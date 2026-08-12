---
tipo: decisao
data: 2026-08-11
status: vigente
---

# DEC-007 - Particionamento por data_referencia

No BigQuery, usar `data_referencia` como campo preferencial de particionamento quando compatível com a natureza temporal da tabela. Usar clustering conforme as chaves reais de consulta. Não replicar a lógica de índices de PostgreSQL.
