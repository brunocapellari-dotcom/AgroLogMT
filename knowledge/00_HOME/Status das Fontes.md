---
tipo: painel
status: vigente
ultima_revisao: 2026-08-12
---

# Status das Fontes

| Fonte | Dados | Pipeline | Prioridade | Próxima ação |
|---|---|---|---|---|
| [[CONAB]] Armazéns | ESTRUTURADA | PRONTO_PARA_CLAUDE_CODE | P0 | carga real BigQuery + snapshot + idempotência |
| [[IMEA]] | ESTRUTURADA | PRONTO_PARA_CLAUDE_CODE | P0 | histórico + atualização segura |
| [[Comex Stat]] | MUITO AVANÇADA | ESPECIFICADA | P0 | localizar CSV completo e carregar |
| [[Portos]] | AVANÇADA | ESPECIFICADA | P0 | separar realizado/programado e implantar histórico |
| [[ANP]] | AVANÇADA | ESPECIFICADA | P0 | jobs por domínio/cadência |
| [[NOAA]] | AVANÇADA | ESPECIFICADA | P1 | freshness + pipeline real |
| [[ANA]] | PARCIAL | ESPECIFICADA | P1 | validar estações e atualização |
| INMET | PARCIAL | ESPECIFICADA | P1 | validar dados reais |
| IBGE | PACOTE ESPECIFICADO | ESPECIFICADA | P1 | executar cargas reais |
| BCB | PACOTE ESPECIFICADO | ESPECIFICADA | P1 | executar cargas reais |
| USDA | PARCIAL | ESPECIFICADA | P1 | completar séries oficiais |
| Argentina | PARCIAL | ESPECIFICADA | P1 | completar séries oficiais |
| SIPEAGRO | AVANÇADA COMO CADASTRO | ESPECIFICADA | P1 | conciliar indústria/capacidade |
| ANTT/RNTRC | PARCIAL | ESPECIFICADA | P1 | completar RNTRC; MDF-e separado |

## Regra

`PRONTO_PARA_CLAUDE_CODE` não significa `INTEGRADA`. Integração exige carga real, logs, DQ, consulta e comportamento idempotente no ambiente alvo.
