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
| Analytics local/backfill | DuckDB + DuckDB Spatial | POC | Inspeção, GeoParquet, backfill, QA e processamento tabular/espacial local de baixo custo; nunca segunda fonte de verdade. |
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
| Grade espacial | H3 (uber/h3 + h3-py) | POC | Grid hierárquico canônico para produção, demanda, tráfego, pressão logística e QA/derivação de geofences AIS; não manter segundo grid padrão sem requisito objetivo. |
| Banco transacional geo | PostGIS | FUTURO | Só quando surgir necessidade transacional/live que BigQuery não atenda. |
| Trajetórias | MobilityDB | FUTURO | Extensão preferencial quando PostGIS entrar para objetos móveis históricos. |
| Geofencing live distribuído | Tile38 | FUTURO | Só promover se geofence em processo não atender escala/latência ou houver múltiplos consumidores de `enter/exit/cross`. |
| Rede OSM / QA | OSMnx + PyOsmium | POC | OSMnx para modelagem/análise local-regional; PyOsmium para PBF bulk/reprodutível. Não são routing service de produção. |
| Map matching | Valhalla/Meili | POC | GPS/track → segmento real de rodovia; FMM fica apenas como benchmark se Valhalla falhar em requisito mensurável. |
| Routing | Valhalla | POC | Engine preferencial único para rotas, matriz OD, isócronas, alternativas e custos de rede. |
| Tiles dinâmicos | Martin | POC | PostGIS/PMTiles → vector tiles quando houver necessidade real de camada dinâmica. |
| Tiles estáticos | PMTiles | CORE | Camadas estáticas em object storage. |
| Geração de tiles | Tippecanoe | POC | Geração/compactação de vector tiles para grandes camadas. |
| Frontend cartográfico | MapLibre | CORE | Base preferencial do mapa operacional. |
| Renderização massiva/replay | deck.gl | POC | Vessel points, trilhas, H3, heading e replay temporal sobre MapLibre. |

## 3.1 Earth Observation e raster cloud-native

| Capacidade | Escolha | Estado | Regra de uso |
|---|---|---:|---|
| Descoberta STAC | PySTAC Client | POC | Cliente padrão quando a fonte expuser STAC; não substituir API oficial simples sem benefício. |
| Carregamento STAC | odc-stac + xarray | POC | Transformar STAC Items em cubos temporais/espaciais para análise e features. |
| NASA Earthdata | earthaccess | POC | Busca, autenticação e acesso/streaming para produtos NASA aprovados. |
| Virtualização HDF/NetCDF | VirtualiZarr | POC | Preferir acesso virtual quando evitar cópia integral e preservar provenance; Kerchunk é fallback/reference. |
| Metadata STAC bulk | STAC-GeoParquet | POC | Snapshot/inventário analítico de Items; não é segundo catálogo de fontes. |
| Raster client-side | deck.gl-raster | POC preferencial | COG/GeoTIFF/Zarr público ou acessível diretamente no browser; evita serviço de tiles quando segurança e volume permitirem. |
| Raster tiles backend | TiTiler | POC condicionado | Usar quando houver dado privado, autorização, transformação server-side, mosaico/política de acesso ou limitação objetiva do client-side. |
| Catálogo/API EO completo | eoAPI | FUTURO / REFERENCIA | Combina pgSTAC/STAC API/raster/vector; não implantar enquanto serviço composto não for necessário. |
| Catálogo STAC próprio | pgSTAC/stac-fastapi | FUTURO | Não implantar enquanto serviço próprio não for necessário; evita Postgres/PostGIS antecipado. |

Fluxo preferencial: `fonte oficial/STAC/Earthdata → RAW/asset reference → catálogo/metadata versionado → xarray/GeoParquet → features/BigQuery → deck.gl-raster quando client-side for seguro/suficiente → TiTiler somente quando backend raster for objetivamente necessário`.

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

O Maritime Intelligence é um subprojeto do AgroLog com runtime próprio, compartilhando contratos, BigQuery, observabilidade e governança. A especificação congelada da V1 está em `docs/MARITIME_INTELLIGENCE_V1.md`.

Stack selecionado:

- código AIS existente do AgroLog — ingestão/normalização e geofence em processo (`CORE` para a V1);
- `pyais` — decoder/encoder NMEA AIVDM/AIVDO aprovado como `POC` para receptores próprios, arquivos NMEA e fallback de baixo nível; não inserir no caminho AISStream JSON já normalizado;
- `MapLibre + deck.gl` — tela operacional, renderização em escala e replay (`CORE/POC`);
- `PMTiles` — camadas cartográficas estáticas (`CORE`);
- `H3` — densidade, pressão espacial e apoio à geração/QA de geofences (`POC`);
- `Tippecanoe` — preparação de vector tiles (`POC`);
- `Martin` — tiles dinâmicos apenas quando a camada live justificar (`POC condicionado`);
- `Tile38` — geofencing distribuído (`FUTURO`, não entra na V1 inicial);
- `PostGIS + MobilityDB` — histórico/trajectórias quando BigQuery/API deixarem de atender (`FUTURO`);
- `OpenCLSim/OpenTNSim` — simulação terminal/hidrovia (`POC`);
- `Veriflow` — verificação de ETA/fila/forecast (`FUTURO` até existir forecast operacional);
- `Redpanda Connect` — integração de streams (`FUTURO` até o volume justificar);
- `RisingWave` — indicadores SQL incrementais/live (`FUTURO` até o volume justificar).

### Geofences operacionais

A V1 não aceita polígonos aproximados como verdade operacional. Prioridade:

1. autoridade portuária/hidrográfica;
2. ENC/S-57/S-101 licenciado/autorizado;
3. OSM/OpenSeaMap como apoio;
4. World Port Index apenas como seed/bounding box;
5. AIS histórico + H3 + DBSCAN para derivação/validação;
6. QA manual contra eventos e line-up conhecidos.

O `UNECE/AIS Berth Polygon Cookbook` é `REFERENCIA` metodológica para H3 + DBSCAN. `SMAC-M` e `s57-parser` são `REFERENCIA` para ingestão/renderização de cartas S-57 quando houver dados legalmente utilizáveis.

### Port-call engine

O engine permanece código próprio do AgroLog. Os patterns de `thanderoy/ais-tracker` — port-call reconstruction, geofence enter/exit, dwell, ship-to-ship proximity, permanência e jobs idempotentes — são ADOPT como patterns, reimplementados/testados internamente; o repositório não entra como dependência, inclusive por não apresentar licença explícita observada. `xang1234/neptune` e `Snaporaz6/ais-vessel-tracker` permanecem `REFERENCIA`. Nenhum deles é fonte de verdade do AgroLog.

### ETA e congestionamento

A primeira etapa é benchmark: ETA AIS, ETA line-up, ETA cinemático e histórico. O primeiro modelo proprietário deve ser tabular/tree-based e combinar AIS + histórico de port calls + fila/clima quando aplicável. `cut-dicl/ais2eta` e literatura recente de AIS + port-call são `REFERENCIA` metodológica.

AISdb permanece `REFERENCIA` por utilidade arquitetural; qualquer incorporação direta exige revisão específica de licença AGPL e implicações de distribuição/serviço.

`MobilityLakehouse` permanece `REFERENCIA/FUTURO` para TemporalParquet/lakehouse de trajetórias; não entra enquanto BigQuery atender o histórico e replay.

## 7. Modelos preditivos e MLOps

| Capacidade | Escolha | Estado |
|---|---|---:|
| Experiment tracking/model registry | MLflow | FUTURO |
| Feature Store | Feast | FUTURO |
| Drift/data/model monitoring | Evidently | FUTURO |
| Performance sem target imediato | NannyML | FUTURO |
| Forecast verification | Veriflow | FUTURO |

Esses componentes só entram após existir ao menos um modelo operacional com dataset point-in-time homologado. Nenhum modelo é promovido apenas por acurácia aparente: exige benchmark, validação fora da amostra, calibração, estabilidade e auditoria de leakage.

## 8. Orquestração, agentes e execução durável

- GitHub Actions, Cloud Run/jobs e os mecanismos existentes continuam atendendo o núcleo operacional.
- n8n permanece candidato para gatilhos/webhooks e automações simples.
- **Pydantic AI + Pydantic AI Harness** passa a `POC` preferencial para agentes analíticos: tipagem, tools, subagentes, planejamento, memória operacional, Step Persistence e OpenTelemetry.
- **LangGraph** fica `REFERENCIA/ALTERNATIVA_CONDICIONAL`; só entra se benchmark mostrar requisito de grafo stateful não atendido adequadamente pelo stack preferencial.
- **Phoenix** fica `POC` para tracing/evals de agentes sobre OpenTelemetry/OpenInference.
- **Promptfoo** fica `POC` para regressão e red-team de prompts/agentes/RAG.
- Temporal permanece `FUTURO`; se durabilidade for necessária, primeiro testar os backends de durable execution já suportados pelo runtime de agentes antes de criar outra camada central.
- Dagster, Airflow e Prefect continuam `NAO_SELECIONADO` como orquestradores gerais para evitar segunda plataforma sem necessidade comprovada.

## 8.1 Engenharia Python

| Capacidade | Escolha | Estado | Regra |
|---|---|---:|---|
| Package/project manager | uv | POC | Benchmark após o primeiro FINAL PASS; não migrar lock/deps durante homologação do PR #187. |
| Lint/format Python | Ruff | POC | Avaliar como gate rápido adicional; não substituir testes, Bandit ou type checks. |
| DAG Python de transformação | Apache Hamilton | REFERENCIA | Benchmark apenas se feature pipelines Python crescerem a ponto de exigir DAG explícito/lineage; não duplicar SQLMesh/dlt/OpenLineage. |

## 9. Tecnologias explicitamente não promovidas ao core agora

As seguintes ferramentas podem ser excelentes, mas não entram no stack principal neste estágio por redundância, prematuridade, licença ou custo operacional:

- Airbyte;
- DataHub;
- OSRM;
- VROOM;
- Soda Core (duplica ODCS/Data Contract CLI + CloudDQ/Pandera e usa Elastic License 2.0);
- pgRouting enquanto PostGIS não for necessário por motivo independente;
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

## 9.1 Benchmarks que não viram segunda ferramenta de produção

- **GraphHopper** — BENCHMARK externo de routing/matrix contra Valhalla; não manter ambos no runtime.
- **Pyrosm** — BENCHMARK de ergonomia/performance PBF→GeoDataFrame contra PyOsmium; apenas um caminho bulk será promovido.
- **Overture Maps** — BENCHMARK/fonte secundária para QA global de rede/entidades; licença dos datasets é revisada separadamente da CLI.
- **MovingPandas** — BENCHMARK offline para trajetórias/stops AIS; não substitui o port-call engine próprio.
- **FMM** — BENCHMARK de map matching caso Valhalla/Meili não atenda precisão/performance exigidas.

Contratos e qualidade permanecem em **ODCS + Data Contract CLI + Pandera quando aplicável + CloudDQ/Dataplex no BigQuery**. Soda Core não é adicionado como segundo engine.

## 10. Sequência de ativação

### Fase 0 — preservar P0/P1

Nenhuma nova plataforma deve atrasar CONAB Armazéns + AgroLog Gateway. Não substituir coletores homologados nem introduzir banco adicional no caminho crítico.

### Fase 1 — qualidade e reprodutibilidade

1. padronizar quality gates reutilizáveis;
2. ampliar contratos existentes em direção a ODCS sem duplicar schemas;
3. testar Pandera em um coletor representativo apenas quando superar o gate existente;
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

1. corrigir/versionar geofences dos cinco portos piloto;
2. aplicar método de QA oficial/ENC/OSM + AIS/H3/DBSCAN;
3. validar port-call engine AIS × geofence × line-up;
4. estruturar MapLibre + deck.gl para live/replay;
5. padronizar GeoParquet/PMTiles para camadas estáticas;
6. manter BigQuery como histórico e medir latência/custo do replay;
7. introduzir PostGIS/MobilityDB, Tile38 ou Martin dinâmico somente diante de gargalo comprovado;
8. só então considerar Redpanda/RisingWave;
9. criar baselines ETA e fila antes de modelos complexos.

### Fase 4 — OD, digital twin e otimização

1. OSMnx/PyOsmium para aquisição, topologia e QA da rede;
2. Valhalla/Meili para routing, matriz OD, isócronas e map matching;
3. AequilibraE para assignment/cenários;
4. UXsim;
5. PyVRP para VRP/frota, mantendo OR-Tools apenas como otimizador geral;
6. OpenTNSim/OpenCLSim;
7. OSRD quando a camada ferroviária possuir dados suficientes.

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


## 13. Benchmark operacional unificado

O gate comparativo de routing/GIS/VRP/AIS fica em:

- `benchmarks/logistics_gis/manifest.v1.json`;
- `scripts/run_logistics_gis_benchmarks.py`;
- `requirements-benchmarks.txt`;
- `tests/test_logistics_gis_benchmark.py`.

O benchmark executa o port-call engine próprio e, quando as dependências/serviços estiverem disponíveis, H3, pyais, PyVRP, Valhalla, PyOsmium e OSMnx. O modo `--strict` transforma qualquer `SKIP` em bloqueio e é o único modo válido para promover POC→CORE.

Dependências de benchmark permanecem isoladas do runtime de produção. Resultado de benchmark é evidência de engenharia, não fonte de verdade analítica.
