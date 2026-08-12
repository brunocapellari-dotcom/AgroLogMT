---
tipo: tecnologia
sistema: AgroLog Gateway
status: planejado_prioritario
ultima_revisao: 2026-08-12
---

# AgroLog Gateway

API/MCP própria em Cloud Run para expor consultas e ações controladas sobre o AgroLog MT.

## Objetivo

Permitir que OpenAI/ChatGPT e Claude consultem a mesma fonte de verdade sem acesso direto irrestrito ao BigQuery.

## Controles

- permissões mínimas;
- logs;
- filtros e contratos semânticos;
- limites de consulta e custo;
- preferir endpoints/views curados em vez de SQL arbitrário;
- ações de escrita somente quando explicitamente autorizadas.

## Primeiro teste

Após CONAB Armazéns estar realmente integrado, executar a mesma consulta através do Gateway por OpenAI/ChatGPT e Claude e comparar resultado/metadados.
