# Backlog Prioritário

## P0 — CONAB Armazéns em produção

- [ ] Confirmar projeto/dataset/tabela de destino no BigQuery real.
- [ ] Executar coletor CONAB Armazéns ponta a ponta.
- [ ] Validar schema e tipos.
- [ ] Validar `data_referencia`, `data_publicacao`, `data_coleta` e `competencia`.
- [ ] Validar deduplicação e idempotência.
- [ ] Validar snapshots e membros de snapshot.
- [ ] Validar particionamento e clustering.
- [ ] Validar logs de execução e contagens.
- [ ] Executar consulta de conferência no BigQuery.
- [ ] Registrar evidências e resultado da primeira carga real.

## P1 — AgroLog Gateway

- [ ] Definir contrato mínimo da primeira ferramenta de consulta.
- [ ] Conectar Cloud Run ao BigQuery com permissões mínimas.
- [ ] Implementar endpoint/ferramenta de leitura para CONAB Armazéns.
- [ ] Adicionar logs e tratamento de erros.
- [ ] Testar a mesma consulta via OpenAI e Claude.

## P2 — Próxima fonte

Somente iniciar após P0 e P1 estarem validados.

Candidata prioritária: **IMEA**, preservando separação por produto e rotina de atualização automática/API/login conforme a fonte permitir.

## Critério de pronto por fonte

Uma fonte só é considerada em produção quando tiver:

- coleta reproduzível;
- schema documentado;
- normalização determinística;
- deduplicação validada;
- histórico preservado quando necessário;
- carga real no BigQuery;
- logs auditáveis;
- consulta de conferência;
- documentação de limitações;
- teste pelo AgroLog Gateway quando aplicável.
