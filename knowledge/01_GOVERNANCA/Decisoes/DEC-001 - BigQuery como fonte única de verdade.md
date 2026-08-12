---
tipo: decisao
data: 2026-08-11
status: vigente
---

# DEC-001 - BigQuery como fonte única de verdade

## Decisão
BigQuery é a fonte única de verdade analítica do AgroLog MT.

## Motivo
O perfil do projeto é analítico, histórico e orientado a cruzamentos. Não há ganho prático comprovado em migrar a camada analítica para Supabase/PostgreSQL.

## Impacto
- tabelas criadas sob demanda;
- particionamento/clustering conforme consultas;
- Cloud Run como camada de execução;
- PostgreSQL reservado a eventual necessidade transacional futura.

## Substitui
Avaliações antigas de DuckDB/Supabase/PostgreSQL como possíveis centros analíticos.
