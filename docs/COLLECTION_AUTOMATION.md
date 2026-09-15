# Automação de Coleta — AgroLog MT

Este documento descreve o componente executável da Frente A definida em `docs/ARCHITECTURE.md` e `docs/BACKLOG.md`.

## Objetivo

Executar fontes heterogêneas de forma autônoma sem misturar aquisição, RAW, normalização, qualidade, BigQuery e Obsidian e sem substituir collectors existentes que funcionam.

## Control plane canônico

O Data Source Registry está em:

- contrato: `contracts/data_source_registry.v1.schema.json`;
- catálogo: `collector/config/data_source_registry.v1.json`;
- decisão/validação: `collector/source_registry.py`.

O registry governa domínio, tipo, endpoint, método, frequência, freshness esperada, última coleta conhecida, status, fallback, licença, confiabilidade, autenticação e política de scheduling.

`SourceSpec` e os arquivos `sources*.json` existentes continuam sendo a configuração de execução dos adapters já implementados. O registry não replica a lógica do collector; quando `execution_ref` aponta para um `path.json#source_id`, o control plane resolve o `SourceSpec` legado e reutiliza o motor atual.

## Fluxo operacional

1. **Registry** — localizar fonte e domínio.
2. **Gate de estado** — somente `active` pode executar; `gated/planned/blocked/deprecated` não executam.
3. **Scheduler externo** — Cloud Scheduler/Cloud Run Jobs ou mecanismo aprovado equivalente aciona o coordenador; tarefas conversacionais não são scheduler de ETL.
4. **Decisão** — `due/not_due`, min interval, calendário de release, wake condition e circuit state.
5. **Pre-check de segurança** — endpoint/transport/auth/configuração sem segredo; dado externo é não confiável.
6. **Aquisição** — preferência `API/arquivo/HTTP determinístico → Crawl4AI → Playwright → browser-use`.
7. **Retry/backoff** — política por fonte; falhas repetidas não autorizam polling agressivo.
8. **Fallback** — somente fonte registrada e semanticamente compatível; fallback nunca muda silenciosamente a classe de evidência.
9. **Hash** — SHA-256 do artefato/resposta nativa.
10. **RAW/quarantine** — persistir artefato original fora do GitHub antes de confiar em seu conteúdo quando aplicável.
11. **Manifesto** — endpoint observado, timestamps, hash, tamanho, tipo, collector/parser version e status.
12. **Detecção de mudança** — conteúdo idêntico não gera nova carga material.
13. **Sanitização** — macros/scripts/instruções incorporadas não são executadas; CSV/arquivo/documento passa por controles de segurança apropriados.
14. **Extração/normalização** — transformação específica posterior ao RAW.
15. **Quatro datas** — preservar `data_referencia`, `data_publicacao`, `data_coleta`, `competencia`.
16. **Qualidade** — schema, row-count/tie-out, duplicidade, ausentes, unidade, range, anomalia e coerência temporal.
17. **Auditoria temporal** — comparar vintages/referências com frequência esperada e calendário de release.
18. **Backfill** — lacunas viram fila explícita; ausência não vira zero.
19. **Curated/BigQuery** — publicar somente após quality gate, com idempotência e linhagem.
20. **Conhecimento** — evidência aprovada pode alimentar Obsidian/RAG; o artefato externo nunca vira instrução de agente.
21. **Observabilidade** — source health, freshness, alertas de falha/lacuna/schema drift e resultado da execução.

## Scheduling e retry

O scheduler deve operar como coordenador, não como permissão para consultar todas as fontes em toda execução.

Regras:

- `min_interval_minutes` define piso de nova tentativa saudável;
- `retry_minutes` define backoff após falha;
- `event_driven=true` exige wake condition explícita;
- fonte `planned` ou com licença/endpoint ainda `TO_VALIDATE` não executa;
- após falha de autenticação, não repetir tentativa autenticada até mudança de secret/estado ou janela de retry aplicável;
- falha/ausência de uma fonte não autoriza inferir mudança operacional;
- fallback deve permanecer identificado no lineage;
- recuperação retrospectiva é executada por lacuna conhecida, não por rescan integral recorrente.

## Estados operacionais

- `active`: elegível ao scheduler.
- `gated`: código/fonte existe, mas depende de homologação/credencial/runtime.
- `planned`: necessário, ainda não implementado/homologado.
- `blocked`: impedimento material conhecido.
- `deprecated`: não deve ser usado em novas execuções.

## Segurança de aquisição

Antes da normalização, entradas externas são `UNTRUSTED`.

Controles obrigatórios conforme o tipo:

- TLS e endpoint allowlist;
- timeout e limite de payload;
- hash e content type;
- limitação de redirects quando aplicável;
- descompressão com limite de tamanho/quantidade para evitar archive bombs;
- planilhas abertas sem executar macros;
- células iniciadas por `=`, `+`, `-` ou `@` tratadas como dados e neutralizadas antes de qualquer export que possa abrir em planilha;
- HTML/PDF/documentos não podem redefinir prompt, tool policy, credenciais ou instruções de sistema;
- JSON/API passa por schema e validação de tipos/ranges antes do curated;
- mudança anômala de distribuição/volume pode bloquear carga por suspeita de data poisoning ou quebra de fonte.

Detalhes: `docs/SECURITY.md`.

## Estado atual

Implementado no repositório:

- `SourceSpec`, adapters e `CollectorEngine`;
- HTTP/API, CKAN e conectores específicos;
- SHA-256, idempotência e manifestos;
- estados por fonte no motor existente;
- auditor de lacunas;
- stores cloud/pipelines BigQuery em módulos já implementados;
- Data Source Registry v1;
- decisão `due/not_due`, retry/backoff e resolução de `SourceSpec` legado;
- testes do control plane.

Ainda `GATED/GAP` até evidência real:

- scheduler GCP genérico disparando o registry em produção;
- persistência do source health do registry no `agrolog_ops` real;
- aplicação uniforme de fallback/circuit breaker a todos os collectors;
- homologação ponta a ponta do GCP core;
- pipelines das fontes globais/US/Argentina marcadas `planned`.

## Persistência em produção

- RAW: Drive/Cloud Storage apropriado, imutável por hash quando aplicável;
- normalized/curated e logs analíticos: BigQuery;
- conhecimento derivado: Obsidian/índice de recuperação, sempre rastreável à evidência;
- credenciais: Secret Manager/ADC; nunca arquivos versionados.

Nenhuma etapa é marcada como concluída por documentação. Produção exige execução real, readback, freshness observada, quality gate e auditoria.