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

## P1A — Piloto de orquestração n8n / CONAB

Pode avançar em paralelo ao P1 somente depois de o pipeline CONAB estar tecnicamente estável. Não bloquear o AgroLog Gateway nem reescrever o collector existente.

- [ ] definir ambiente controlado de n8n e estratégia de secrets;
- [ ] criar workflow mínimo para verificar atualização da CONAB Armazéns;
- [ ] baixar/preservar o original e registrar checksum/metadados quando houver mudança;
- [ ] acionar o collector existente sem duplicar sua lógica no workflow;
- [ ] preservar idempotência do pipeline;
- [ ] registrar execução, status, contagens e erros;
- [ ] validar caminho manual de reprocessamento sem n8n;
- [ ] comparar resultado automatizado com a execução manual já validada;
- [ ] documentar rollback, limitações e operação;
- [ ] aprovar o piloto antes de expandir a IMEA ou outras fontes.

Issue de implementação: #36.

## P2 — Próxima fonte

Somente iniciar após P0 e P1 estarem validados. O piloto P1A deve estar aprovado antes de usar n8n como padrão de automação para novas fontes.

Candidata prioritária: **IMEA**, preservando separação por produto e rotina de atualização automática/API/login conforme a fonte permitir.

## P3 — Camada local de IA / Ollama

Somente iniciar após existir volume operacional suficiente para benchmark real.

- [ ] selecionar conjunto representativo de documentos/tarefas;
- [ ] comparar Ollama com modelos de nuvem em precisão, tempo, custo e taxa de erro;
- [ ] limitar uso inicial a classificação, metadados, triagem ou extrações simples;
- [ ] não promover para produção sem ganho demonstrável;
- [ ] avaliar integração posterior via AI Router/n8n sem criar segunda fonte de verdade.

## P4 — Otimização de contexto/tokens

- [ ] avaliar Caveman apenas com benchmark interno;
- [ ] não comprimir `CLAUDE.md`, `AGENTS.md` ou documentação canônica sem teste de perda de instruções e revisão explícita.

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
