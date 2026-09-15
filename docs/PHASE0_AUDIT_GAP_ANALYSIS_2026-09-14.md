# Fase 0 — Auditoria e Gap Analysis do AgroLog MT

Data de corte da auditoria: 2026-09-14 (America/Cuiaba)

Esta auditoria compara o estado real do repositório com a arquitetura oficial do AgroLog MT. Ela não substitui `docs/ARCHITECTURE.md`; registra evidência de implementação e lacunas. A regra é conservadora: documentação ou fonte citada sem collector/storage/teste não é tratada como módulo operacional.

## 1. Escopo oficial

Prioridade operacional da plataforma:

`Mato Grosso → Brasil → América do Sul → Estados Unidos → Mundo`

O AgroLog deve operar como plataforma de inteligência do agronegócio global, mantendo Mato Grosso como maior prioridade operacional e conectando produção, mercado, clima, logística, hidrologia, energia, indústria, pecuária, comércio, notícias e forecast.

## 2. Legenda de maturidade

- `IMPLEMENTED`: código/contrato/teste correspondente existe no repositório.
- `PARTIAL`: parte relevante existe, mas falta ao menos uma etapa do critério operacional.
- `GATED`: implementação existe, porém depende de homologação, credencial, fonte real ou gate externo.
- `PLANNED`: fonte/capacidade está registrada, mas collector/pipeline operacional não existe.
- `GAP`: capacidade requerida e ainda não encontrada no repositório.
- `N/A`: não é necessária no desenho atual.

`IMPLEMENTED` não significa automaticamente `PRODUCTION`. Produção exige homologação do runtime real, freshness observada e gates de segurança/qualidade.

## 3. Inventário técnico encontrado

### Coleta e normalização

O repositório contém collectors/adapters reais para:

- CONAB Armazéns e CONAB Safra, incluindo BigQuery, histórico e vintages;
- Comex Stat API/arquivos, BigQuery e pipeline;
- IMEA workbook autorizado, migração, normalização e BigQuery;
- IBGE PAM, localidades/malhas e BigQuery;
- BCB PTAX;
- ANA HidroWebService;
- NASA POWER, grade climática e BigQuery;
- Copernicus Climate;
- ANP bioenergia;
- AIS/AISStream, line-up HTML/PDF, lifecycle, reconciliação e BigQuery;
- notícias/sinais editoriais;
- conectores genéricos CKAN e Socrata;
- CFTC COT;
- USDA AgTransport.

Também existem adapters/configurações ainda gated para USDA FAS PSD, ESR e GATS.

### Dados e storage

- BigQuery é a fonte de verdade analítica canônica.
- RAW é preservado fora do GitHub com SHA-256/manifestos quando o pipeline usa o motor canônico.
- `collector/cloud_store.py` implementa a ponte de persistência cloud do núcleo atual.
- PostGIS não está adotado no runtime; permanece `FUTURO`. BigQuery GIS/GeoParquet/MapLibre atendem o desenho atual.
- Não há evidência no repositório de uma camada PostGIS operacional ou de banco transacional em produção.

### Pipelines e automação

Existem:

- `CollectorEngine`, adapters e manifests;
- Cloud Run Jobs/deploy scripts;
- GitHub Actions para probes, backfills, homologação e modelos;
- retry/reconexão específico em AIS e políticas específicas em alguns pipelines;
- auditoria de lacunas e point-in-time.

Lacuna central: não existe ainda um Data Source Registry único e executável com domínio, freshness, status, fallback, licença e confiabilidade, nem um scheduler genérico que decida `due/not_due/backoff` a partir desse registro.

### Modelos e forecast

O repositório contém primitives N6 para:

- point-in-time;
- baselines;
- feature matrix;
- datasets de treino;
- avaliação e promoção;
- agroclima;
- hidrologia;
- pressão/logística;
- reconciliação marítima;
- primeiros backtests.

Ainda não existem modelos operacionais completos e promovidos para toda a lista: produção, yield, clima, preços, estoques, exportações, frete, ETA e congestionamento. Forecast vintage é requisito transversal ainda sem contrato canônico único.

### Conhecimento e agentes

- GitHub/Claude/Codex/ChatGPT possuem governança de engenharia definida.
- Obsidian está definido como Segundo Cérebro, mas `docs/OBSIDIAN.md` ainda é mínimo e não prova ingestão/autonomia de conhecimento por domínio.
- LangGraph é candidato, não runtime promovido.
- Os especialistas analíticos globais pedidos nesta arquitetura ainda não possuem contrato canônico de papéis, ferramentas, inputs, outputs e limites.

## 4. Matriz do critério operacional

Cada linha é avaliada contra: **Coleta (C), Normalização (N), Armazenamento (S), Freshness (F), Qualidade (Q), Análise (A), Modelos (M), Conhecimento (K), Relatórios (R), Alertas (L), Testes (T)**.

| Domínio | C | N | S | F | Q | A | M | K | R | L | T | Estado principal |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Core MT / Soja MT | IMPLEMENTED | IMPLEMENTED | GATED | PARTIAL | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | GATED por homologação GCP |
| Brasil — safra/produção | IMPLEMENTED | IMPLEMENTED | GATED | PARTIAL | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | CONAB/IBGE fortes; expansão incompleta |
| Brasil — mercado/comércio | IMPLEMENTED | IMPLEMENTED | GATED | PARTIAL | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | Comex/PTAX prontos em código; CEPEA não tem collector encontrado |
| EUA — safra | PARTIAL | PARTIAL | GAP | GAP | PARTIAL | GAP | GAP | PARTIAL | GAP | GAP | PARTIAL | FAS/AgTransport existem; WASDE/NASS ainda GAP |
| Argentina — safra | GAP | GAP | GAP | GAP | GAP | GAP | GAP | PARTIAL | GAP | GAP | GAP | SAGyP/BCR/Bolsa de Cereales ausentes no runtime |
| Global supply & demand | PARTIAL | GAP | GAP | GAP | GAP | GAP | GAP | PARTIAL | GAP | GAP | PARTIAL | PSD metadata existe; motor de balanço ainda GAP |
| Weather/climate | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | NASA/Copernicus; INMET/CPTEC/NOAA-CPC incompletos |
| Hydrology | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | ANA + modelos; Madeira/Tapajós precisam produto operacional próprio |
| Logística terrestre | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | ANTT/MDFe/frete ainda não fecham stack completo |
| Maritime | IMPLEMENTED | IMPLEMENTED | GATED | PARTIAL | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | núcleo AIS/line-up forte; runtime real ainda gated |
| Energia/diesel | PARTIAL | PARTIAL | PARTIAL | GAP | PARTIAL | GAP | GAP | PARTIAL | GAP | GAP | PARTIAL | ANP/PTAX existem; Brent/Petrobras/tributos/event-study faltam |
| Indústria — etanol | PARTIAL | PARTIAL | PARTIAL | GAP | PARTIAL | PARTIAL | GAP | PARTIAL | GAP | GAP | PARTIAL | ANP existe; ANEEL/ONS/matéria-prima integrados ainda faltam |
| Indústria — esmagamento | GAP | GAP | GAP | GAP | GAP | GAP | GAP | PARTIAL | GAP | GAP | GAP | ABIOVE/capacidade/processamento sem collector encontrado |
| Gado | GAP | GAP | GAP | GAP | GAP | GAP | GAP | PARTIAL | separado | GAP | GAP | SIGSIF/IBGE/export/preço/clima/alimentação não integrados |
| News Impact | IMPLEMENTED | IMPLEMENTED | PARTIAL | PARTIAL | PARTIAL | PARTIAL | GAP | PARTIAL | PARTIAL | PARTIAL | IMPLEMENTED | sinal existe; cadeia causal formal ainda incompleta |
| Forecast transversal | N/A | PARTIAL | GAP | GAP | PARTIAL | PARTIAL | PARTIAL | PARTIAL | GAP | GAP | IMPLEMENTED | primitives N6 existem; forecast vintage e modelos operacionais faltam |
| Relatórios/editorial | N/A | N/A | PARTIAL | PARTIAL | PARTIAL | PARTIAL | N/A | PARTIAL | PARTIAL | PARTIAL | PARTIAL | templates existem; Report Editor AI ainda não runtime |
| Agentes/Segundo Cérebro | N/A | N/A | PARTIAL | GAP | PARTIAL | PARTIAL | N/A | GAP | PARTIAL | PARTIAL | PARTIAL | governança existe; execução analítica multiagente ainda GAP |
| Segurança/observabilidade | N/A | N/A | PARTIAL | PARTIAL | PARTIAL | N/A | N/A | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PR de hardening existe; backup/restore e runtime real ainda gaps |

## 5. Fontes: presente, parcial e ausente

### Brasil — encontradas no código/configuração

- CONAB — collectors para armazéns e safra.
- IMEA — pipeline de workbook autorizado e BigQuery.
- IBGE — PAM, localidades e malhas.
- Comex Stat — API, backfill, BigQuery e validação.
- BCB — PTAX.
- ANA — HidroWebService.
- ANP — bioenergia.
- ANTT — CKAN/fundações, incluindo ferrovias.
- ANTAQ/Marinha/DNIT — fontes registradas para hidrologia/navegabilidade e marítimo em diferentes níveis.

### Brasil — fontes prioritárias sem collector operacional encontrado nesta auditoria

- CEPEA;
- ANEEL;
- ONS;
- ABIOVE;
- SIGSIF operacional para o módulo de gado;
- INMET como pipeline canônico;
- CPTEC como pipeline canônico.

Essas fontes permanecem preservadas no catálogo conceitual, mas não devem ser marcadas como operacionais até existir fonte → collector → storage → normalização → validação → análise → conhecimento → relatório/alerta → teste.

### Estados Unidos

Encontrado:

- USDA FAS PSD/ESR/GATS registrados e gated;
- USDA AgTransport com client/datasets/tests;
- CFTC COT;
- NASA POWER como clima auxiliar.

Gaps prioritários:

- WASDE com preservação de vintage;
- NASS Quick Stats;
- Crop Progress;
- Crop Production;
- Acreage;
- Prospective Plantings;
- Grain Stocks;
- Export Sales materializado em tabelas canônicas;
- Weekly Weather & Crop Bulletin;
- NOAA/CPC;
- camada satélite agrícola dedicada;
- harmonização soja/milho/algodão/trigo.

### Argentina

Não foram encontrados collectors operacionais canônicos para:

- SAGyP;
- BCR/GEA;
- Bolsa de Cereales;
- clima/satélite argentino dedicado;
- séries USDA/FAS explicitamente materializadas como módulo Argentina.

### Global

Gaps prioritários:

- motor de balanço global por commodity;
- ingestão/versionamento WASDE/PSD/AMIS/IGC/FAO + bases nacionais;
- balanceamento canônico de estoque inicial, produção, importação, oferta, consumo, processamento, exportação, estoque final e stock/use;
- reconciliação de unidades e marketing years;
- vintage point-in-time por release.

## 6. Gap Analysis por programa

### P0 — Control plane de fontes

Implementar sem substituir adapters existentes:

1. Data Source Registry canônico.
2. Validador de registry e vínculo com `SourceSpec` existente.
3. Scheduler por metadata (`due/not_due/blocked/backoff`).
4. Source health, freshness e retry/fallback comuns.
5. Estado operacional em BigQuery `agrolog_ops` quando o runtime GCP estiver homologado.

### P1 — EUA + balanço global

1. WASDE vintages.
2. NASS/Crop Progress/Crop Production/Acreage/Prospective Plantings/Grain Stocks.
3. Export Sales/FAS/PSD canônicos.
4. NOAA/CPC e Weather & Crop Bulletin.
5. Global Supply & Demand Engine com commodity/country/marketing-year/vintage.

### P2 — Argentina

1. SAGyP.
2. BCR/GEA.
3. Bolsa de Cereales.
4. clima/satélite.
5. harmonização com USDA/FAS.

### P3 — Energia, indústria e gado

1. Diesel Engine: ANP + Petrobras + Brent + USD/BRL + importação + biodiesel + tributos + política de preços + notícias.
2. Event studies, correlação e lags com frete/custo agrícola.
3. Etanol: ANP + ANEEL + ONS + matérias-primas.
4. Crushing: ABIOVE + empresas + capacidade + processamento.
5. Cattle: SIGSIF + IBGE + exportação + preço + clima + alimentação.

### P4 — Hidrovias estratégicas

Criar produtos específicos para Madeira e Tapajós sobre o núcleo existente:

- nível;
- vazão;
- chuva;
- tendência;
- percentil;
- mínimos/máximos;
- navegabilidade;
- restrições;
- terminais;
- impactos em Miritituba/Santarém/Barcarena/Arco Norte.

### P5 — News Impact e causalidade

Evoluir `news_signals` para preservar explicitamente:

`evento → mecanismo → commodity → mundo → Brasil → Mato Grosso`

Cada relação deve ser classificada como:

- correlação;
- hipótese causal;
- causalidade sustentada.

Texto externo nunca é instrução para agente; é evidência não confiável até sanitização/classificação.

### P6 — Forecast

Criar contrato transversal de forecast vintage e promover modelos somente após backtest point-in-time:

- produção;
- yield;
- clima;
- preços;
- estoques;
- exportações;
- frete;
- ETA;
- congestionamento.

## 7. Segurança — gaps remanescentes

O PR de hardening adiciona WIF por IDs imutáveis, Secret Manager, Actions pinadas, containers não-root, Gateway privado e scanners. Permanecem como gates:

- `CI_EXECUTION_BLOCKER`: no estado auditado, jobs do PR de segurança falharam antes de receber runner (`runner_id=0`, sem steps), portanto não há evidência de falha funcional dos testes, mas o PR não pode ser promovido até o CI executar normalmente;
- branch/ruleset real de `main` ainda precisa ser aplicado e lido de volta;
- GCP/WIF real ainda precisa de bootstrap/homologação por identidade humana autorizada;
- backup/restore testado ainda não está evidenciado;
- política executável contra CSV injection, malicious files, archive bombs e prompt injection precisa ser adicionada aos pipelines de ingestão documental/tabular;
- source authentication/API spoofing deve ser verificada por TLS + domínio/endpoint allowlist + hash/signature quando a fonte oferecer mecanismo verificável.

## 8. Critério de pronto por módulo

Um módulo só pode ser classificado `OPERATIONAL` quando existir evidência para todos os blocos abaixo:

1. fonte;
2. collector;
3. storage;
4. normalização;
5. validação;
6. análise;
7. conhecimento;
8. relatório ou alerta;
9. teste.

Freshness é um gate transversal obrigatório. Modelos são obrigatórios quando o módulo declara capacidade preditiva; caso contrário podem ser `N/A` de forma explícita.

Qualquer etapa ausente mantém o módulo em `PARTIAL`, `GATED` ou `GAP` e deve aparecer no backlog canônico.

## 9. Resultado da Fase 0

O AgroLog já possui um núcleo técnico relevante para MT/Brasil, qualidade point-in-time, marítimo e ingestão heterogênea. A principal mudança arquitetural necessária não é reescrever o núcleo, e sim:

1. transformar o catálogo disperso em control plane executável;
2. completar cobertura EUA/Argentina/global;
3. fechar energia/indústria/gado;
4. transformar conhecimento/agentes em runtime governado;
5. persistir forecasts por vintage;
6. promover segurança e GCP somente com evidência real.

A execução deve continuar incrementalmente, preservando collectors que já funcionam.