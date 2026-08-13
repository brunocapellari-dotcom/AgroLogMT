# Backlog Prioritário

## P0 — CONAB Armazéns no BigQuery real

- [x] Confirmar projeto/dataset de destino no BigQuery real.
- [x] Executar carga CONAB Armazéns ponta a ponta.
- [x] Validar schema e tipos do grupo Armazéns.
- [x] Preservar campos temporais conforme disponibilidade da fonte.
- [x] Validar deduplicação e idempotência.
- [x] Validar snapshots e membros de snapshot.
- [x] Validar logs de execução e contagens.
- [x] Executar consulta de conferência no BigQuery.
- [x] Registrar evidências e resultado da primeira carga real.
- [x] Corrigir e validar em execução real o contador de movimento da carga histórica.

**Marco:** piloto CONAB Armazéns validado em 13/08/2026. Estado consolidado: 18.807 armazéns, 1 snapshot COMPLETO e 18.807 membros; MT com 2.917 armazéns, 107 municípios e 58.368.190 t. A terceira execução idêntica resultou em `novos=0`, `alterados=0`, `inalterados=18.807`, `ausentes=0`, sem duplicação analítica.

Pendências da fonte CONAB que não reabrem o piloto de Armazéns:
- validar coleta HTTP ao vivo ponta a ponta;
- implantar execução automatizada em Cloud Run/Cloud Scheduler;
- validar gradualmente as demais famílias CONAB antes de tratá-las como produção.

## P1 — AgroLog Gateway

- [ ] Definir contrato mínimo da primeira ferramenta de consulta.
- [ ] Conectar Cloud Run ao BigQuery com permissões mínimas.
- [ ] Implementar endpoint/ferramenta de leitura para `logistica.vw_armazens_atuais`.
- [ ] Adicionar logs e tratamento de erros.
- [ ] Testar a mesma consulta via OpenAI/Codex e Claude.

Issue operacional: #13 — AgroLog Gateway para Armazéns.

## P1 paralelo — Engenharia multiagente

- [ ] Instalar/autenticar Codex no notebook.
- [ ] Validar `codex mcp-server` com Claude Code.
- [ ] Rodar teste sem alteração e teste documental pequeno.
- [ ] Adotar revisão Claude → Codex para mudanças materiais quando o MCP estiver disponível.

## P2 — Automação CONAB

- [ ] Definir armazenamento RAW permanente no Google Cloud.
- [ ] Validar download oficial de Armazéns.
- [ ] Executar validação/circuit breaker antes da publicação.
- [ ] Implantar Cloud Run Job.
- [ ] Implantar Cloud Scheduler.
- [ ] Registrar falhas e quarentenas sem publicar snapshot suspeito.

## P2 paralelo — Próxima fonte

Candidata prioritária: **IMEA**, preservando separação por produto e rotina de atualização automática/API/login conforme a fonte permitir.

A preparação de IMEA pode avançar em paralelo, mas cada família só entra em produção depois de cumprir seu próprio critério de pronto.

## Critério de pronto por fonte

Uma fonte/família só é considerada em produção quando tiver:

- coleta ou carga reproduzível;
- schema documentado;
- normalização determinística;
- deduplicação validada;
- histórico preservado quando necessário;
- carga real no BigQuery;
- logs auditáveis;
- consulta de conferência;
- documentação de limitações;
- teste pelo AgroLog Gateway quando aplicável.
