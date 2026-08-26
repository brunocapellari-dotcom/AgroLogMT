# Stack Tecnológico Canônico — AgroLog MT

Este documento registra as **escolhas tecnológicas de implementação** do AgroLog MT. Ele complementa `docs/ARCHITECTURE.md`, que continua sendo a fonte canônica da arquitetura técnica. Em caso de conflito, `docs/ARCHITECTURE.md` prevalece.

A regra principal é: **não instalar ferramentas por antecipação**. Uma tecnologia aprovada entra no runtime somente quando existir caso de uso concreto, teste, benefício mensurável, revisão de licença/segurança e estratégia de saída.

## Estados de adoção

- `CORE`: padrão preferencial para novas implementações quando a capacidade for necessária.
- `POC`: aprovado para prova controlada antes de produção.
- `FUTURO`: aprovado conceitualmente, mas só entra quando escala/caso de uso justificar.
- `REFERENCIA`: usar arquitetura, algoritmo ou metodologia; não assumir dependência de runtime.
- `NAO_SELECIONADO`: alternativa avaliada que não deve competir com o componente preferencial sem falha objetiva de requisito.

## 1. Data Platform

| Capacidade | Escolha | Estado | Regra de uso |
|---|---|---:|---|
| Warehouse analítico | BigQuery | CORE | Fonte única de verdade analítica. |
| RAW | Google Cloud Storage/Drive apropriado | CORE | Artefato original imutável, hash e metadados quando aplicável. |
| Ingestão Python/API | dlt | POC | Preferencial para fontes novas quando reduzir código; não reescrever coletor homologado só para padronizar. |
| ETL tabular | Polars | POC | Preferencial para cargas grandes; Pandas apenas onde compatibilidade/simplicidade justificar. |
| Analytics local/backfill | DuckDB | POC | Inspeção, Parquet, backfill, QA e processamento local de baixo custo. |
| Validação Python | Pandera | POC | Quality gate antes da persistência analítica quando DataFrame for a abstração adequada. |
| Contrato de dados | ODCS + Data Contract CLI | POC | Evoluir os contratos atuais sem criar segunda definição concorrente. |
| Transformação SQL | SQLMesh | POC | Avaliar sobre BigQuery para backfill seguro, ambientes e controle de mudança. |
| Qualidade no warehouse | CloudDQ/Dataplex | POC | Regras de integridade, freshness, duplicidade, ranges e consistência no BigQuery. |
| Lineage | OpenLineage | POC | Padrão de eventos de execução e proveniência. |
| Catálogo/metadata | OpenMetadata | FUTURO | Entra após P0/P1 quando houver massa crítica de datasets/pipelines; integra contratos, lineage e glossário. |
| Governança SQL | SQLGlot | POC | Parsing, lineage de coluna, lint e políticas AgroLog. |
| Observabilidade técnica | OpenTelemetry Collector | POC | Métricas/traces/logs de coletores, gateway e serviços. |
| Documentos/PDF | Docling | POC | Primeiro candidato para estrutura e tabelas, preservando página/evidência. |
| CSV/Excel | Frictionless | POC | Inspeção estrutural de arquivos antes da normalização quando agregar valor. |

### Regra de integração com o código atual

Os coletores existentes permanecem válidos. `dlt`, Polars, Pandera, DuckDB ou qualquer outro componente não justificam migração automática. Migração ocorre apenas quando reduzir complexidade, custo, falha operacional ou dívida técnica de forma demonstrável.

## 2. Temporalidade, vintages e reprodutibilidade

O AgroLog preserva explicitamente, quando aplicável:

- `data_referencia`;
- `data_publicacao`;
- `data_coleta`;
- `competencia`;
- versão/vintage da fonte;
- hash do artefato;
- versão do coletor/parser/transformação.

Dolt, lakeFS e XTDB permanecem `REFERENCIA` arquitetural. O conceito de versionamento/bitemporalidade deve ser implementado primeiro com GCS + BigQuery + contratos/vintages existentes. Não adicionar banco/lakehouse paralelo sem necessidade comprovada.

## 3. Geoespacial

| Capacidade | Escolha | Estado | Regra de uso |
|---|---|---:|---|
| Conversão/ETL geo | GDAL | CORE | Conversão e normalização de formatos geoespaciais. |
| Arquivo geo analítico | GeoParquet | CORE | Formato preferencial para novos artefatos vetoriais analíticos. |
| Grade espacial | H3 | POC | Agregação espacial hierárquica para produção, demanda, tráfego e pressão logística. |
| Banco transacional geo | PostGIS | FUTURO | Só quando surgir necessidade transacional/live que BigQuery não atenda. |
| Trajetórias | MobilityDB | FUTURO | Extensão preferencial quando PostGIS entrar para objetos móveis históricos. |
| Geofencing live | Tile38 | POC | Primeiro candidato para `enter/exit/cross` de AIS/GPS e áreas operacionais. |
| Map matching | FMM | POC | GPS/track → segmento real de rodovia. |
| Routing | Valhalla | POC | Engine preferencial de rotas e custos de rede. |
| Tiles dinâmicos | Martin | POC | PostGIS/PMTiles → vector tiles quando houver mapa operacional. |
| Tiles estáticos | PMTiles | CORE | Camadas estáticas em object storage. |
| Geração de tiles | Tippecanoe | POC | Geração/compactação de vector tiles para grandes camadas. |
| Frontend cartográfico | MapLibre | CORE | Base preferencial do mapa operacional. |

## 4. Matriz OD, rodovias e otimização

| Capacidade | Escolha | Estado |
|---|---|---:|
| Rede/matriz OD/assignment | AequilibraE | POC |
| Otimização geral | OR-Tools | POC |
| VRP/backhaul/frota | PyVRP | POC |
| Simulação corredor/BR-163 | UXsim | POC |
| Simulação microscópica | SUMO | FUTURO |
| Planejamento multimodal | FTOT | REFERENCIA |

A ordem lógica é: `OD canônica → rede/rotas → assignment → observação real/map matching → simulação → otimização`.

## 5. Hidrovias, terminais e ferrovias

| Capacidade | Escolha | Estado |
|---|---|---:|
| Tráfego hidroviário | OpenTNSim | POC |
| Cadeia logística/terminal | OpenCLSim | POC |
| Filas especializadas | OpenQTSim | FUTURO |
| Dimensionamento terminal | OpenTISim | FUTURO |
| Modelagem hidrológica | HydroMT | FUTURO |
| Ferrovia/capacidade/timetable | OSRD | FUTURO |
| PySeidon/berth-allocation acadêmico | Projetos de referência | REFERENCIA |

## 6. AgroLog Maritime Intelligence

O Maritime Intelligence é um subprojeto do AgroLog com runtime próprio, compartilhando contratos, BigQuery, observabilidade e governança.

Stack selecionado:

- `pyais` — decode/normalização inicial AIS (`POC`);
- `Tile38` — geofences operacionais (`POC`);
- `PostGIS + MobilityDB` — histórico/trajectórias quando necessário (`FUTURO` até a necessidade transacional);
- `H3` — densidade/pressão espacial (`POC`);
- `PMTiles + Martin + MapLibre` — mapa operacional (`POC/CORE` conforme a camada);
- `OpenCLSim/OpenTNSim` — simulação terminal/hidrovia (`POC`);
- `Veriflow` — verificação de ETA/fila/forecast (`FUTURO` até existir forecast operacional);
- `Redpanda Connect` — integração de streams (`FUTURO` até o volume justificar);
- `RisingWave` — indicadores SQL incrementais/live (`FUTURO` até o volume justificar).

AISdb é `REFERENCIA` por utilidade arquitetural; qualquer incorporação direta exige revisão específica de licença AGPL e implicações de distribuição/serviço.

## 7. Modelos preditivos e MLOps

| Capacidade | Escolha | Estado |
|---|---|---:|
| Experiment tracking/model registry | MLflow | FUTURO |
| Feature Store | Feast | FUTURO |
| Drift/data/model monitoring | Evidently | FUTURO |
| Performance sem target imediato | NannyML | FUTURO |
| Forecast verification | Veriflow | FUTURO |

Esses componentes só entram após existir ao menos um modelo operacional com dataset point-in-time homologado. Nenhum modelo é promovido apenas por acurácia aparente: exige benchmark, validação fora da amostra, calibração, estabilidade e auditoria de leakage.

## 8. Orquestração e execução durável

- GitHub Actions, Cloud Run/jobs e os mecanismos existentes continuam atendendo o núcleo atual.
- n8n permanece candidato para gatilhos/webhooks e automações simples, conforme arquitetura atual.
- LangGraph permanece candidato preferencial para orquestração de agentes analíticos stateful.
- Temporal fica `FUTURO` para workflows realmente duráveis, longos e com recovery/human-in-the-loop; não instalar enquanto retry/checkpoint dos componentes atuais forem suficientes.
- Dagster, Airflow e Prefect ficam `NAO_SELECIONADO` no momento para evitar uma segunda plataforma de orquestração sem necessidade comprovada.

## 9. Tecnologias explicitamente não promovidas ao core agora

As seguintes ferramentas podem ser excelentes, mas não entram no stack principal neste estágio por redundância, prematuridade, licença ou custo operacional:

- Airbyte;
- DataHub;
- OSRM;
- VROOM;
- NVIDIA cuOpt;
- Apache Sedona/SedonaDB;
- Apache Iceberg;
- lakeFS;
- Dolt;
- XTDB;
- DuckLake;
- Materialize;
- Pathway;
- Kepler.gl.

Uma delas pode ser promovida no futuro se o componente preferencial falhar em requisito objetivo ou se a escala justificar.

## 10. Sequência de ativação

### Fase 0 — preservar P0/P1

Nenhuma nova plataforma deve atrasar CONAB Armazéns + AgroLog Gateway. Não substituir coletores homologados nem introduzir banco adicional no caminho crítico.

### Fase 1 — qualidade e reprodutibilidade

1. padronizar quality gates reutilizáveis;
2. ampliar contratos existentes em direção a ODCS sem duplicar schemas;
3. testar Pandera em um coletor representativo;
4. testar DuckDB/Polars em uma carga pesada/reprocessamento;
5. testar SQLGlot para lint/lineage de SQL;
6. testar CloudDQ sobre uma tabela BigQuery homologada;
7. instrumentar source health/telemetria mínima.

### Fase 2 — ingestão e transformação

1. comparar `dlt` com um coletor novo real;
2. testar SQLMesh em ambiente BigQuery isolado;
3. adotar OpenLineage apenas depois de existir execução suficiente para justificar lineage operacional;
4. avaliar OpenMetadata somente após lineage/contratos/qualidade possuírem sinais reais.

### Fase 3 — geoespacial e Maritime

1. padronizar GeoParquet;
2. criar H3 canônico;
3. estruturar camadas PMTiles/MapLibre;
4. PoC de Tile38 com geofences AIS;
5. validar port-call engine AIS × line-up;
6. introduzir PostGIS/MobilityDB apenas se a necessidade live/transacional for comprovada;
7. só então considerar Redpanda/RisingWave.

### Fase 4 — OD, digital twin e otimização

1. AequilibraE;
2. Valhalla/FMM;
3. UXsim;
4. PyVRP/OR-Tools;
5. OpenTNSim/OpenCLSim;
6. OSRD quando a camada ferroviária possuir dados suficientes.

### Fase 5 — MLOps

Feast/MLflow/Evidently/NannyML/Veriflow entram apenas junto de modelos operacionais homologados.

## 11. Critérios de promoção de POC para CORE

Uma tecnologia só pode ser promovida quando:

1. resolve um problema real e documentado;
2. possui licença/termos compatíveis com o uso esperado;
3. tem manutenção e segurança aceitáveis;
4. possui teste executável no AgroLog;
5. não cria segunda fonte de verdade;
6. não duplica ferramenta canônica sem justificativa;
7. tem estratégia de saída/substituição;
8. mede benefício em confiabilidade, custo, desempenho ou velocidade de desenvolvimento;
9. preserva provenance, temporalidade e classificação epistemológica do AgroLog;
10. não compromete P0/P1 nem introduz custo de infraestrutura sem necessidade.

## 12. Princípio final

O produto é o AgroLog MT. Ferramentas são substituíveis. A infraestrutura deve permanecer mínima, auditável, modular e proporcional ao problema real.
