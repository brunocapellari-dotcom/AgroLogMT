---
tipo: mapa
status: vigente
ultima_revisao: 2026-08-12
---

# Mapa de Dados

## Fluxo

Fontes oficiais/autorizadas → Google Cloud Storage (raw) → BigQuery staging → DQ → BigQuery curado → [[AgroLog Gateway]] → agentes/relatórios.

## Domínios

- Agro: safra, progresso, comercialização, oferta/demanda, custos.
- Mercado: preços físicos, CBOT, câmbio, prêmios, paridades.
- Comércio exterior: [[Comex Stat]].
- Logística: fretes, armazéns, RNTRC, infraestrutura.
- Portos: movimentação, escalas e line-up.
- Clima: NOAA/INMET.
- Hidrologia: ANA, Tapajós e Madeira.
- Indústria: unidades, capacidade, processamento e bioenergia.
- Macro: BCB.
- Internacional: USDA e Argentina.

## Fonte única de verdade

[[BigQuery]] contém fatos e séries analíticas. Drive não substitui o warehouse; Obsidian não copia históricos completos.
