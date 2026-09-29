# Arquitetura do AgroLog MT

## Missão oficial

O AgroLog MT é uma plataforma de inteligência do agronegócio global com prioridade operacional hierárquica:

`Mato Grosso → Brasil → América do Sul → Estados Unidos → Mundo`

A prioridade geográfica define profundidade operacional, frequência e ordem de resposta; ela não limita o universo de análise. O sistema deve explicar como mudanças globais de oferta, demanda, clima, energia, comércio e logística se transmitem até Brasil e Mato Grosso e, no sentido inverso, como mudanças relevantes em Mato Grosso alteram fluxos nacionais e globais.

A evolução continua incremental. Nenhum collector homologado é substituído apenas para padronizar tecnologia ou atender uma arquitetura teórica.

## Critério operacional obrigatório por módulo

Todo módulo classificado como `OPERATIONAL` deve possuir evidência para:

1. fonte;
2. collector;
3. storage;
4. normalização;
5. validação;
6. análise;
7. conhecimento;
8. relatório ou alerta;
9. teste.

`Freshness` é gate transversal. Modelos são obrigatórios somente quando o módulo declara capacidade preditiva; nesses casos também são obrigatórios vintage, cutoff point-in-time, benchmark e avaliação fora da amostra.

Uma etapa ausente mantém o módulo em `PARTIAL`, `GATED` ou `GAP` e deve aparecer em `docs/PHASE0_AUDIT_GAP_ANALYSIS_2026-09-14.md` e no backlog canônico.

## Domínios de inteligência

O AgroLog opera os seguintes domínios conectados:

- produção, safra, área, produtividade, fenologia e estoques;
- clima/agroclima e sensoriamento remoto;
- mercado global e balanço mundial de oferta/demanda;
- mercado Brasil/MT, preços físicos, câmbio, basis, prêmios e comercialização;
- safra dos Estados Unidos;
- safra da Argentina/América do Sul;
- comércio exterior;
- logística terrestre, armazenagem, ferrovia, rodovia e fretes;
- inteligência marítima, portos, line-up, AIS, ETA e congestionamento;
- hidrologia/navegabilidade, com produtos explícitos para Madeira e Tapajós;
- energia/diesel e transmissão de custos;
- agroindústria, etanol e esmagamento;
- pecuária de corte, editorialmente separada do relatório agrícola/logístico principal;
- inteligência comercial;
- notícias e impacto causal possível;
- forecast e cenários;
- relatórios, alertas e Segundo Cérebro.

## Data Source Registry e coleta autônoma

`collector/config/data_source_registry.v1.json` é o control plane canônico de fontes. Ele não substitui `SourceSpec`, adapters ou configurações legadas que funcionam; agrega metadados de governança e decisão operacional.

Campos mínimos por fonte:

- `source_id`, nome, domínio e tipo;
- URL/API/endpoint;
- método de aquisição;
- frequência e freshness esperada;
- última coleta conhecida;
- status (`active`, `gated`, `planned`, `blocked`, `deprecated`);
- fallbacks;
- licença/termos;
- confiabilidade;
- autenticação, classe de segurança e referência de execução quando disponível.

Métodos suportados conceitualmente: REST API, WebSocket, FTP/SFTP, CSV, XLSX, JSON, HTML, RSS, STAC, BigQuery, download oficial, MCP e stream.

O scheduler de produção deve consultar o registry e executar somente fontes `active`, respeitando `due/not_due`, publicação esperada, freshness, retry/backoff, circuit breaker, wake condition e fallback. `planned` e `gated` nunca são promovidos implicitamente a coleta real.

A implementação inicial de decisão está em `collector/source_registry.py`; Cloud Scheduler/Cloud Run Jobs ou mecanismo aprovado equivalente continuará sendo o gatilho durável de produção.

## Cobertura geográfica e fontes prioritárias

### Mato Grosso e Brasil

Preservar e ampliar as fontes já catalogadas, incluindo CONAB, IMEA, IBGE, CEPEA, Comex Stat, ANTAQ, ANTT, ANP, ANEEL, ONS, ABIOVE, SIGSIF, BCB, ANA, INMET, CPTEC e demais fontes oficiais/especializadas já aprovadas.

### Estados Unidos

Cobertura mínima:

- USDA WASDE;
- USDA NASS Quick Stats;
- Crop Progress;
- Crop Production;
- Acreage;
- Prospective Plantings;
- Grain Stocks;
- Export Sales/FAS;
- PSD;
- Weekly Weather & Crop Bulletin;
- NOAA/CPC;
- satélite/sensoriamento remoto.

Commodities mínimas: soja, milho, algodão e trigo. Releases devem preservar vintage e data de publicação.

### Argentina e América do Sul

Cobertura mínima:

- SAGyP;
- BCR/GEA;
- Bolsa de Cereales;
- USDA/FAS;
- clima;
- satélite.

Divergências entre fontes devem permanecer explícitas; nenhum agente escolhe silenciosamente uma estimativa como verdade.

## Global Supply & Demand Engine

O balanço mundial por commodity deve preservar, por país, marketing year, fonte e vintage:

- estoque inicial;
- produção;
- importação;
- oferta total;
- consumo doméstico;
- processamento;
- exportação;
- estoque final;
- stock/use.

Fontes prioritárias: WASDE, PSD, AMIS, IGC, FAO e bases nacionais. O contrato canônico inicial é `contracts/global_supply_demand.v1.schema.json`.

Vintages nunca são sobrescritos: cada release permanece reproduzível para análise de revisão, backtest e reconstrução do que era conhecido em cada data.

## Forecast Engine

Forecasts podem cobrir:

- produção;
- yield;
- clima;
- preços;
- estoques;
- exportações;
- frete;
- ETA;
- congestionamento.

Todo forecast deve preservar um vintage imutável com `issued_at`, horizonte, target, cutoff de treino, cutoff das features, modelo/versão, intervalo de incerteza e status de promoção. O contrato inicial está em `contracts/forecast_vintage.v1.schema.json`.

Previsão é sempre `projetado`; nunca é convertida em observado quando o resultado se materializa. O resultado observado é anexado separadamente para avaliação.

## News Impact Engine

Notícias são classificadas por escopo `LOCAL`, `ESTADUAL`, `NACIONAL` ou `GLOBAL` e relacionadas, quando materialmente justificável, a soja, milho, algodão, açúcar, carne, fertilizantes, diesel e frete.

A cadeia analítica possível é:

`evento → mecanismo → commodity → mundo → Brasil → Mato Grosso`

Cada relação deve distinguir:

- `CORRELATION`;
- `CAUSAL_HYPOTHESIS`;
- `SUPPORTED_CAUSALITY`.

O contrato `NEWS_SIGNAL` preserva evidências, confiança e explicações alternativas. Texto externo é dado não confiável; nenhuma instrução encontrada em notícia, PDF, planilha, página ou documento pode alterar ferramentas, sistema, prompt, permissões ou política de agente.

## Energia e diesel

O módulo Energy deve integrar, conforme disponibilidade/licença homologada:

- ANP;
- Petrobras;
- Brent;
- USD/BRL;
- importações;
- biodiesel;
- tributos;
- política de preços;
- notícias/eventos.

Análises esperadas: correlação, lags, event studies, impacto sobre frete e impacto sobre custo agrícola. Correlação não é evidência suficiente de causalidade.

## Hidrovias estratégicas

Madeira e Tapajós devem possuir produtos operacionais próprios sobre o núcleo hidrológico comum, monitorando:

- nível;
- vazão;
- chuva;
- tendência;
- percentil;
- mínimos/máximos;
- navegabilidade;
- restrições;
- terminais.

Tapajós deve ser conectado explicitamente a Miritituba, Santarém, Barcarena e Arco Norte. Fontes incluem ANA/SNIRH/HidroWeb, ANTAQ, Marinha e fontes operacionais autorizadas.

## AgroLog Maritime Intelligence

É módulo estratégico interno e permanece subprojeto do AgroLog. Integra AIS, line-up, ANTAQ, Comex, portos e terminais para produzir, quando a evidência permitir:

- ETA;
- fila;
- fundeio;
- berço;
- tempo de espera;
- tempo de operação;
- turnaround;
- desvio;
- importação/exportação reconciliadas.

AIS, programação portuária e realizado permanecem observações distintas. A V1 específica continua em `docs/MARITIME_INTELLIGENCE_V1.md`.

## Indústria e pecuária

### Etanol

Integrar ANP + ANEEL + ONS + matérias-primas. Sinais de geração/capacidade são evidência indireta de operação industrial quando não houver produção observada.

### Esmagamento

Integrar ABIOVE + empresas + capacidade + processamento, preservando periodicidade mensal e limites de cobertura.

### Gado

Integrar SIGSIF + IBGE + exportações + preços + clima + alimentação. O Cattle Intelligence compartilha dados, governança e Segundo Cérebro, mas mantém produto editorial próprio.

## Agentes de inteligência

O contrato canônico é `contracts/ai_roles.v1.json`. Papéis oficiais:

- AGROLOG CHIEF INTELLIGENCE AI;
- CROP AI;
- WEATHER AI;
- GLOBAL MARKET AI;
- BRAZIL MARKET AI;
- US CROP AI;
- ARGENTINA CROP AI;
- LOGISTICS AI;
- MARITIME AI;
- HYDROLOGY AI;
- ENERGY AI;
- INDUSTRIAL AI;
- CATTLE AI;
- COMMERCIAL INTELLIGENCE AI;
- NEWS IMPACT AI;
- FORECAST AI;
- REPORT EDITOR AI;
- AUDITOR AI.

Agentes analíticos são consumidores governados do AgroLog Gateway e do Segundo Cérebro; não constituem fontes de verdade e não recebem acesso irrestrito direto ao BigQuery. Nenhum agente publica automaticamente, altera RAW/IAM ou promove inferência a observado.

A evolução derivada do Radar GitHub continua organizada como **três frentes integradas da mesma arquitetura**:

- **Frente A — coleta, documentos e qualidade**;
- **Frente B — inteligência, conhecimento e observabilidade**;
- **Frente C — expansão operacional e comercial**.

Essas frentes podem ser desenvolvidas em paralelo, mas novas fontes e integrações reais só entram em produção após os critérios de qualidade, segurança e governança aplicáveis. BigQuery, GitHub, RAW/Drive/Cloud Storage, AgroLog Gateway e Obsidian mantêm suas responsabilidades canônicas.

## Princípio de seleção tecnológica

O AgroLog não acumula frameworks equivalentes. Cada capacidade deve ter uma responsabilidade principal e uma rota de substituição.

Seleção atual do Radar para provas controladas:

- **LangGraph** — candidato preferencial para orquestração dos agentes analíticos;
- **Crawl4AI** — candidato para coleta/extração de conteúdo público preparado para pipelines e RAG;
- **Whisper** — candidato para transcrição de áudio/vídeo autorizado;
- **LibreChat** — candidato para cockpit interno de IA sobre o AgroLog Gateway;
- **Polymarket Public API/SDK** — sinal experimental somente leitura para expectativa macro/geopolítica;
- **Ollama** — candidato preferencial para inferência local futura;
- **VectorBT** — laboratório quantitativo interno, não dependência central do produto;
- **HyperFrames** — publicação automatizada futura, fora do núcleo analítico;
- **code-server** — conveniência opcional de engenharia, fora do AgroLog Core.

TradingAgents, Vibe-Trading, Fincept Terminal e awesome-quant são referências/benchmarks; Open WebUI, Dify, Markdoc e llama.cpp permanecem condicionais conforme `docs/AI_TOOLING.md`.

## Camadas

1. **Fontes externas**
   - Data Source Registry governa fontes oficiais, especializadas, secundárias e experimentais;
   - páginas, portais, arquivos, APIs e canais autorizados de comunicação;
   - áudio/vídeo público ou autorizado quando houver valor informacional e direito de processamento;
   - sinais externos experimentais sempre identificados por natureza e limitações;
   - dados operacionais autorizados de clientes em etapas futuras.

2. **Aquisição e monitoramento de fontes**
   - coletores específicos por fonte;
   - APIs e conectores padronizados quando disponíveis;
   - hierarquia preferencial `API/arquivo/HTTP determinístico → Crawl4AI → Playwright → browser-use`;
   - detecção de publicação, versão, hash, alteração ou novo artefato;
   - scheduler orientado ao registry, retry/backoff, circuit breaker, fallback e processamento por diferença.

3. **Inteligência documental, áudio e multimodal**
   - extração de texto, tabelas e metadados;
   - parsing multimodal aprovado;
   - Whisper ou componente aprovado para transcrição autorizada;
   - classificação e sanitização antes de persistência analítica;
   - artefato original no RAW, nunca no GitHub.

4. **RAW → normalized → curated, qualidade e linhagem**
   - RAW imutável quando aplicável, hash e metadata;
   - normalização determinística;
   - schema validation, row-count/tie-out, duplicidade, range, unidade e temporalidade;
   - detecção de anomalia e data poisoning;
   - registro da versão do collector/parser/transformação;
   - bloqueio de publicação quando quality gate falha;
   - prevenção explícita de look-ahead bias.

5. **BigQuery**
   - fonte única de verdade analítica;
   - tabelas criadas sob demanda;
   - particionamento por `data_referencia` quando aplicável;
   - clustering por chaves de consulta;
   - vintages preservados para fontes revisáveis e forecasts;
   - classes de evidência permanentemente distinguíveis.

6. **AgroLog Gateway**
   - Cloud Run/API/MCP própria;
   - permissões mínimas e logs;
   - sem exposição direta do banco;
   - acesso obrigatório para agentes, cockpit e futuros produtos externos.

7. **Camada de conhecimento e recuperação**
   - Obsidian como Segundo Cérebro permanente;
   - conhecimento técnico, histórico, causal e contextual;
   - não substitui GitHub nem BigQuery;
   - RAG/vetores são índices, nunca fonte de verdade;
   - toda síntese material deve apontar evidência recuperável.

8. **Agentes de inteligência e engenharia**
   - ChatGPT/OpenAI: coordenação, governança e manutenção do GitHub;
   - Claude Code: executor principal no notebook, testes e operações GCP/BigQuery;
   - Codex: segundo agente de engenharia e revisor independente;
   - agentes analíticos seguem `contracts/ai_roles.v1.json`;
   - LangGraph permanece candidato preferencial para orquestração stateful após benchmark;
   - debate de agentes nunca substitui evidência, DQ ou teste executável.

9. **Cockpit interno de IA**
   - LibreChat é candidato preferencial;
   - `LibreChat → AgroLog Gateway → dados/ferramentas autorizados`;
   - autenticação/RBAC/logs/isolamento obrigatórios antes de piloto.

10. **BI, observabilidade e geointeligência**
   - BI para exploração analítica;
   - observabilidade técnica separada;
   - geointeligência para produção, rotas, armazenagem, indústria, corredores, portos e fluxos;
   - PostGIS permanece `FUTURO`; BigQuery GIS/GeoParquet são preferidos até existir gargalo/requisito transacional comprovado.

11. **Laboratório quantitativo e avaliação de hipóteses**
   - backtests, walk-forward, sensibilidade e validação de sinais separados de produção;
   - todo estudo respeita vintages/data de corte;
   - hipótese validada entra em produção somente por contrato, teste e governança.

12. **Sinais macro/geopolíticos experimentais**
   - sinais externos são complementares e explicitamente classificados;
   - nenhum sinal substitui fonte oficial ou dado físico;
   - uso somente leitura quando houver mercado/plataforma externa experimental.

13. **IA local e roteamento futuro**
   - Ollama é candidato preferencial para tarefas locais/privadas ou de alto volume quando benchmark justificar;
   - modelos locais não substituem automaticamente modelos de maior qualidade;
   - evitar servidores redundantes sem requisito objetivo.

14. **Publicação e experiência externa**
   - ferramentas de publicação recebem somente números/conclusões já aprovados;
   - publicação nunca recalcula indicador nem altera conclusão analítica.

15. **Engenharia e acesso ao ambiente**
   - ferramentas remotas de desenvolvimento ficam fora do runtime;
   - qualquer exposição exige autenticação forte, HTTPS/Zero Trust e least privilege;
   - segredos nunca entram no frontend ou GitHub.

16. **Expansão operacional e comercial**
   - integração futura com telemetria/frota, IoT e visão computacional;
   - dados de clientes somente autorizados e isolados;
   - produtos externos consomem interfaces controladas.

## Freight Listener — canal autorizado de ofertas de frete

O Freight Listener é módulo da Frente C. Fluxo conceitual:

```text
Canal autorizado
→ adaptador isolado
→ webhook/fila
→ classificação
→ extração
→ normalização/deduplicação/auditoria
→ BigQuery
→ Freight Market Signal Engine / BI / mapa / agentes
```

Regras:

- adaptador de WhatsApp desacoplado do núcleo;
- mensagens RAW/mídia não entram no GitHub;
- oferta anunciada é `observado` com subtipo de oferta observada, não frete realizado;
- contratado/executado permanecem desconhecidos sem evidência operacional;
- PII é minimizada/pseudonimizada;
- repostagens são agrupadas;
- reoferta/reajuste/persistência são sinais derivados;
- especificação canônica: `docs/FREIGHT_LISTENER.md`.

## Fontes de verdade por responsabilidade

- GitHub: código, SQL, schemas, testes, configuração sem segredo, contratos e documentação.
- BigQuery: dados estruturados e histórico analítico oficial.
- RAW/Drive/Cloud Storage: artefatos originais e documentos de fonte.
- Obsidian: conhecimento derivado, contexto, relações e memória histórica.

## Segurança e fronteira de confiança

Todo dado externo é **não confiável até validação**. O fluxo padrão é:

`UNTRUSTED EXTERNAL → quarantine/RAW → validation/sanitization → normalized → quality gate → curated`

Controles mínimos:

- segregação RAW/normalized/curated;
- SHA-256 e provenance;
- schema validation e row-count/tie-out;
- freshness e anomaly detection;
- autenticação da fonte quando aplicável;
- TLS e allowlist de endpoint/domínio;
- Secret Manager, WIF e RBAC;
- backups/restore testados antes de declarar recuperação operacional;
- audit logs;
- defesas contra data poisoning, CSV injection, arquivos maliciosos/archive bombs, API spoofing, prompt injection documental e supply-chain attacks.

Detalhes canônicos ficam em `docs/SECURITY.md`.

## Regras estruturais

- Não manter bases separadas por IA.
- Não criar fontes concorrentes entre GitHub, BigQuery e Obsidian.
- Não criar dezenas de tabelas vazias antecipadamente.
- Criar datasets/tabelas conforme a fonte/módulo entra em produção.
- PostgreSQL/PostGIS somente quando surgir necessidade transacional real que BigQuery não atenda.
- Toda fonte entra com origem, frequência, granularidade, cobertura, licença/termos, limitações, freshness e classe de evidência.
- Revisão por segundo agente não substitui testes executáveis.
- Componentes open source são substituíveis e exigem revisão de licença, segurança, manutenção e estratégia de saída.
- Não adotar duas plataformas completas para a mesma função sem requisito objetivo.
- Nenhum status de produção é inferido de documentação: exige runtime real, freshness observada, quality gate e evidência de homologação.


## AgroLog 360 analytical layer

`marts_agrolog360` é a camada derivada compartilhada por Gateway, cockpit e agentes. Ela não substitui datasets canônicos de origem.

Primeiros marts:
- clima rolling 7/15/30/60/90;
- balanço produção/capacidade estática;
- corredores/fretes observados;
- importações de fertilizantes;
- biomassa com semântica de evidência explícita;
- overview corrente para o cockpit.

O aplicador `scripts/apply_agrolog360_marts.py` verifica dependências reais antes de criar o dataset/view. Isso preserva a regra de não criar tabelas vazias antecipadamente.

### Biomassa

Biomassa mantém a distinção metodológica entre potencial estimado, geração observada, movimentação florestal observada e consumo industrial declarado. A camada analítica não converte um sinal indireto em consumo físico observado.

### Cockpit

O mesmo AgroLog Gateway serve Maritime Intelligence e o overview AgroLog 360. Falha/ausência de um mart não pode transformar dado inexistente em zero nem derrubar uma capacidade independente já disponível.
