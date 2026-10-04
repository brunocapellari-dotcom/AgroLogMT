# AgroLog MT

Repositório central do projeto **AgroLog MT**.

## Missão

Construir uma plataforma de inteligência do agronegócio global com prioridade operacional:

`Mato Grosso → Brasil → América do Sul → Estados Unidos → Mundo`

O AgroLog conecta produção, clima, mercados, oferta e demanda, comércio exterior, logística, hidrologia, energia, indústria, pecuária, notícias e forecast para explicar impactos globais e locais e apoiar decisão com evidência rastreável.

Mato Grosso continua sendo o núcleo de maior profundidade operacional. A expansão global não substitui nem atrasa os gates reais do core MT/Brasil.

## Arquitetura oficial

- **BigQuery** — fonte única de verdade analítica.
- **RAW/Drive/Cloud Storage** — artefatos originais, documentos e evidências pesadas, com hash/proveniência quando aplicável.
- **Cloud Run** — execução de collectors/jobs e serviços.
- **AgroLog Gateway** — API/MCP própria para consultas e ações controladas, sem acesso irrestrito ao banco.
- **Data Source Registry** — control plane de fontes, freshness, status, retry, fallback, licença e confiabilidade.
- **ChatGPT/OpenAI** — coordenação, governança, arquitetura e consolidação do GitHub.
- **Claude Code** — executor principal no ambiente local para implementação, testes e GCP/BigQuery.
- **Codex** — segundo agente de engenharia e revisor técnico independente.
- **Obsidian** — Segundo Cérebro para conhecimento técnico, histórico, causal e contextual.
- **Agentes de Inteligência** — conselho especializado governado pelo Gateway, contratos e AUDITOR AI.
- **PostgreSQL/PostGIS** — somente se surgir necessidade transacional/geoespacial live que BigQuery não atenda; não entram por antecipação.

### Critério operacional

Um módulo só é `OPERATIONAL` quando existe evidência para:

`fonte → collector → storage → normalização → validação → análise → conhecimento → relatório/alerta → teste`

Freshness, segurança, lineage, observabilidade e restore são gates transversais. Se houver forecast, também são obrigatórios vintage, cutoff point-in-time, benchmark e avaliação.

Etapa ausente implica `PARTIAL`, `GATED`, `BLOCKED` ou `GAP` — nunca “pronto por documentação”. A promoção objetiva usa `contracts/source_promotion_gate.v1.schema.json` e `collector/source_promotion.py`.

## Coleta autônoma

O control plane está dividido em:

- `contracts/data_source_registry.v1.schema.json` — contrato;
- `collector/config/data_source_registry.v1.json` — catálogo global;
- `collector/source_registry.py` — validação, due/not_due, backoff, source health e resolução de collectors existentes;
- `collector/registry_scheduler.py` — planejamento e retry/fallback orientados ao registry;
- `CollectorEngine` e adapters atuais — execução, preservados quando funcionam;
- Cloud Scheduler/Cloud Run Jobs — gatilho durável de produção após homologação.

Fontes `planned`, `gated`, `blocked` ou `deprecated` não podem ser executadas como se fossem produção. Retry/fallback não autoriza trocar silenciosamente natureza da evidência.

## Cobertura de inteligência

### Mato Grosso / Brasil

CONAB, IMEA, IBGE, CEPEA, Comex Stat, ANTAQ, ANTT, ANP, ANEEL, ONS, ABIOVE, SIGSIF, BCB, ANA, INMET, CPTEC e demais fontes homologadas conforme estágio real do collector.

### Estados Unidos

WASDE, NASS/Quick Stats, Crop Progress, Crop Production, Acreage, Prospective Plantings, Grain Stocks, Export Sales/FAS, PSD, Weekly Weather & Crop Bulletin, NOAA/CPC e sensoriamento remoto, inicialmente para soja, milho, algodão e trigo.

### Argentina / América do Sul

SAGyP, BCR/GEA, Bolsa de Cereales, USDA/FAS, clima e satélite, mantendo divergências e vintages explícitos.

### Global Supply & Demand

Balanços por commodity/país/marketing year/vintage: estoque inicial, produção, importação, oferta, consumo, processamento, exportação, estoque final e stock/use. Fontes-alvo incluem WASDE, PSD, AMIS, IGC, FAO e bases nacionais.

## Agentes de Inteligência

Papéis canônicos em `contracts/ai_roles.v1.json`:

- AGROLOG CHIEF INTELLIGENCE AI
- CROP AI
- WEATHER AI
- GLOBAL MARKET AI
- BRAZIL MARKET AI
- US CROP AI
- ARGENTINA CROP AI
- LOGISTICS AI
- MARITIME AI
- HYDROLOGY AI
- ENERGY AI
- INDUSTRIAL AI
- CATTLE AI
- COMMERCIAL INTELLIGENCE AI
- NEWS IMPACT AI
- FORECAST AI
- REPORT EDITOR AI
- AUDITOR AI

Agentes não são fonte de verdade, não alteram RAW/IAM e não tratam instruções encontradas em notícia/documento como instruções do sistema.

## Segurança de dados e informação

Todo conteúdo externo começa como **não confiável**:

`UNTRUSTED EXTERNAL → RAW/QUARANTINE → VALIDATION/SANITIZATION → NORMALIZED → QUALITY GATE → CURATED`

Controles incluem:

- SHA-256 e provenance;
- schema e row-count/tie-out;
- freshness e anomaly detection;
- WIF/OIDC, Secret Manager e RBAC;
- TLS/endpoint validation;
- containers non-root e Gateway privado;
- controles contra data poisoning, CSV formula injection, arquivos maliciosos/archive bombs, API spoofing, prompt injection documental e supply-chain attacks;
- backup/restore somente considerado operacional depois de restore testado;
- audit logs e incident response.

Política canônica: `docs/SECURITY.md`. Runbook de recuperação: `docs/BACKUP_RESTORE.md`.

## Programa Integrado Radar

As melhorias tecnológicas permanecem três frentes da mesma arquitetura:

1. **Coleta, documentos e qualidade**.
2. **Inteligência, conhecimento e observabilidade**.
3. **Expansão operacional e comercial**.

Componentes open source são peças substituíveis. Não reescrever collector homologado apenas para padronizar framework.

## Freight Listener

O Freight Listener transforma mensagens e mídias de **canais autorizados** em observações estruturadas de ofertas de frete. Oferta anunciada não prova contratação, execução nem frete pago. O módulo mantém PII minimizada, deduplicação e evidência fora do GitHub.

## Inteligência geopolítica externa

O Geopolitical Watch é projeto independente e pode fornecer eventos/sinais por interface versionada. O AgroLog preserva a evidência recebida e faz análise própria de relevância para agricultura, energia, fertilizantes, câmbio, comércio e logística.

## Documentação principal

- `docs/ARCHITECTURE.md` — arquitetura oficial global.
- `docs/PHASE0_AUDIT_GAP_ANALYSIS_2026-09-14.md` — auditoria e Gap Analysis da Fase 0.
- `docs/SECURITY.md` — segurança de dados, identidade, ingestão, runtime e incidentes.
- `docs/BACKUP_RESTORE.md` — política operacional de backup, restore drill e critérios de recuperação verificada.
- `docs/TECHNOLOGY_STACK.md` — seleção tecnológica e gates de promoção.
- `docs/DATA_GOVERNANCE.md` — governança dos dados/evidências.
- `docs/REPOSITORY_GOVERNANCE.md` — governança do GitHub.
- `docs/COLLECTION_AUTOMATION.md` — coleta autônoma e scheduler orientado ao registry.
- `docs/AI_TOOLING.md` — ferramentas e Radar Tecnológico.
- `docs/MULTI_AGENT_WORKFLOW.md` — engenharia + conselho de inteligência.
- `docs/OBSIDIAN.md` — Segundo Cérebro e knowledge state.
- `docs/N6_PROGRAM.md` / `docs/N6_EXECUTION_STATUS.md` — rigor quantitativo e estado N6.
- `docs/SOY_MT_DATAMART.md` — primeiro Data Mart vertical.
- `docs/MARITIME_INTELLIGENCE_V1.md` — inteligência marítima.
- `docs/FREIGHT_LISTENER.md` — inteligência de ofertas observadas.
- `docs/AGROLOG360_OPERATIONAL_EXPANSION.md` — marts, indicadores, cockpit e expansão operacional 51–100.
- `docs/BACKLOG.md` — backlog executável.

Contratos novos centrais:

- `contracts/data_source_registry.v1.schema.json`;
- `contracts/source_promotion_gate.v1.schema.json`;
- `contracts/restore_drill.v1.schema.json`;
- `contracts/ai_roles.v1.json`;
- `contracts/global_supply_demand.v1.schema.json`;
- `contracts/forecast_vintage.v1.schema.json`;
- `contracts/news_signal.v0_5.schema.json`;
- `contracts/agrolog_observation.v1.schema.json`;
- `contracts/source_quality_freshness.v1.json`;
- `contracts/agrolog360_marts.v1.json`.

## Fontes de verdade

- **GitHub** — código, collectors, schemas, contratos, SQL, testes e documentação.
- **RAW/Drive/Cloud Storage** — artefatos originais e históricos pesados.
- **BigQuery** — dados estruturados e histórico analítico oficial.
- **Obsidian** — conhecimento derivado e memória histórica.

Não manter uma base por IA nem duplicar contratos entre essas camadas.

## Temporalidade e evidência

Preservar, quando aplicável:

- `data_referencia`;
- `data_publicacao`;
- `data_coleta`;
- `competencia`;
- vintage/source version/hash/collector version.

Classificar explicitamente:

- `observado`;
- `estimado`;
- `projetado`;
- `inferido`;
- `sinal_qualitativo`;
- `negociado_autorizado`.

`data_referencia` não é data de disponibilidade. Backtests só usam dados/vintages disponíveis no corte.

## Prioridade executiva atual

### Gates que bloqueiam produção

1. **PR #187 / #159:** provisionar runner GCE efêmero `agrolog-ci` ou executar o finalizador integral diretamente no Cloud Shell/GCP; o workflow canônico permanece enfileirado quando não há runner.
2. **#160:** o compartilhamento Drive do collector já foi revalidado como resolvido; falta executar a homologação GCP real de CONAB Armazéns + AgroLog Gateway até `N6 CORE HOMOLOGATION: PASS`.
3. Executar o Full Project Final Gate no mesmo SHA, com zero LIVE skips, Trivy/SBOM/Gitleaks/history, runtime security, freshness/data quality e restore drill, até `AGROLOG MT FINAL RELEASE: PASS`.
4. **#183:** somente após o PASS integral, promover exatamente o SHA validado e aplicar/readback das proteções canônicas de `main`.

### Capacidades preparadas no candidato, ainda não promovidas

- runtime de agentes: Pydantic AI + Harness selecionado como POC preferencial; integração externa ainda não ativada;
- avaliação de agentes: contrato e gate fail-closed próprios implementados, com testes;
- Earth Observation: contrato de provenance de assets + métricas NDVI/EVI/LAI/LST preparados; STAC/Earthdata permanecem POC;
- sinais comerciais: vetores de condições de venda do produtor e demanda 30d implementados sem score/forecast não calibrado;
- nenhuma dessas capacidades é considerada produção antes do gate integral.

### Expansão que pode avançar em paralelo sem ativação prematura

1. Consolidar Data Source Registry, scheduler e source promotion gate sobre collectors existentes.
2. Fechar Brasil/MT + Maritime.
3. Fechar EUA + Global Supply & Demand.
4. Fechar Argentina/América do Sul.
5. Completar diesel/energia, indústria e gado.
6. Transformar Madeira/Tapajós em produtos hidrológicos operacionais.
7. Promover News Impact e Forecast somente com vintages/quality/backtests.
8. Transformar agentes/Segundo Cérebro em runtime governado após os dados subjacentes estarem homologados.

> Evoluir incrementalmente; preservar collectors funcionais; nunca declarar produção sem runtime real, freshness observada, quality gate, restore verificado e evidência.
