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

Freshness é gate transversal. Se houver forecast, também são obrigatórios vintage, cutoff point-in-time, benchmark e avaliação.

Etapa ausente implica `PARTIAL`, `GATED` ou `GAP` — nunca “pronto por documentação”.

## Coleta autônoma

O control plane está dividido em:

- `contracts/data_source_registry.v1.schema.json` — contrato;
- `collector/config/data_source_registry.v1.json` — catálogo global;
- `collector/source_registry.py` — validação, due/not_due, backoff e resolução de collectors existentes;
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

Política canônica: `docs/SECURITY.md`.

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
- `docs/BACKLOG.md` — backlog executável.

Contratos novos centrais:

- `contracts/data_source_registry.v1.schema.json`;
- `contracts/ai_roles.v1.json`;
- `contracts/global_supply_demand.v1.schema.json`;
- `contracts/forecast_vintage.v1.schema.json`;
- `contracts/news_signal.v0_5.schema.json`.

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

1. Resolver o `CI_EXECUTION_BLOCKER` do hardening: os jobs do PR de segurança precisam efetivamente receber runner e executar os testes.
2. Homologar CONAB Armazéns + AgroLog Gateway no GCP real e obter `N6 CORE HOMOLOGATION: PASS`.
3. Aplicar/readback das proteções de `main`, WIF/IAM/secrets e validar runtime privado/least privilege.

### Expansão que pode avançar em paralelo sem ativação prematura

1. Consolidar Data Source Registry e scheduler genérico sobre collectors existentes.
2. Fechar EUA + Global Supply & Demand.
3. Fechar Argentina/América do Sul.
4. Completar diesel/energia, indústria e gado.
5. Transformar Madeira/Tapajós em produtos hidrológicos operacionais.
6. Promover News Impact e Forecast somente com vintages/quality/backtests.
7. Transformar agentes/Segundo Cérebro em runtime governado após os dados subjacentes estarem homologados.

> Evoluir incrementalmente; preservar collectors funcionais; nunca declarar produção sem runtime real, freshness observada, quality gate e evidência.