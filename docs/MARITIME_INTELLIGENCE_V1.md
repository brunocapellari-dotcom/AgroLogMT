# AgroLog Maritime Intelligence — Arquitetura V1 congelada

Status: `FROZEN_V1`
Data de corte arquitetural: 2026-08-26

Este documento congela a arquitetura de implementação da V1 do AgroLog Maritime Intelligence após a rodada final de pesquisa técnica. Ele é subordinado às regras gerais de `docs/ARCHITECTURE.md`, `docs/TECHNOLOGY_STACK.md`, `docs/DATA_GOVERNANCE.md` e ao contrato `contracts/shipping_reconciliation.v1.json`.

Mudanças conceituais nesta V1 só devem ocorrer diante de evidência prática de que um requisito não pode ser atendido pela arquitetura abaixo.

## 1. Objetivo da V1

Construir uma tela operacional no estilo MarineTraffic, mas voltada à inteligência logística do AgroLog, capaz de:

- acompanhar embarcações AIS nos portos piloto;
- reconstruir automaticamente port calls;
- separar aproximação, fundeio, atracação, desatracação e saída;
- confrontar AIS com line-up portuário;
- medir fila, espera, permanência e divergências de ETA;
- preservar histórico e permitir replay temporal;
- gerar métricas reproduzíveis por porto, terminal, navio e janela temporal;
- manter distinção rigorosa entre observado, informado, estimado e inferido.

A V1 não deve afirmar carga efetiva, comprador, trading ou volume contratado sem fonte autorizada.

## 2. Portos piloto canônicos

1. `SANTOS`
2. `PARANAGUA`
3. `BARCARENA_VILA_DO_CONDE`
4. `SANTAREM`
5. `ITAQUI`

Miritituba/Itaituba continua relevante para a cadeia hidroviária/logística, mas não substitui Itaqui no piloto marítimo principal.

## 3. Arquitetura mínima da V1

```text
AISStream / fonte AIS autorizada
        ↓
parser/normalização existente
        ↓
quality gate + provenance
        ↓
geofence em processo
        ↓
BigQuery histórico
        ↓
port-call engine
        ↓
reconciliação AIS × line-up × operação observada
        ↓
API/Gateway
        ↓
MapLibre + deck.gl
```

Princípio: não adicionar serviço distribuído quando o runtime atual resolver o requisito com qualidade suficiente.

## 4. Interface cartográfica

### Componentes selecionados

- `MapLibre GL JS` — basemap, câmera, interação cartográfica e camadas vetoriais;
- `deck.gl` — renderização de alto volume e replay temporal;
- `PMTiles` — camadas estáticas em object storage;
- `Tippecanoe` — preparação de tiles quando necessário;
- `Martin` — somente quando houver necessidade comprovada de tiles dinâmicos sobre PostGIS/PMTiles.

### Uso previsto do deck.gl

- `ScatterplotLayer`/camada equivalente para embarcações;
- `PathLayer` para heading/rotas curtas;
- `TripsLayer` para histórico e replay;
- H3 layers quando densidade espacial for útil;
- atualização incremental em vez de redesenhar toda a frota.

A referência técnica da V1 inclui demonstrações públicas do ecossistema vis.gl capazes de renderizar aproximadamente 20 mil embarcações live com MapLibre + deck.gl, trilhas AIS e dead reckoning visual.

### Regra de frontend

O frontend não acessa BigQuery diretamente. Dados live/históricos são entregues por API/Gateway controlado.

## 5. Geofences — regra canônica

Não usar marcador aproximado nem polígono inventado para fundeadouro, canal ou berço.

Ordem preferencial de evidência:

1. geometria oficial da autoridade portuária/hidrográfica quando disponível e licenciável;
2. ENC/S-57/S-101 ou outra carta náutica oficial/autorizada;
3. OpenStreetMap/OpenSeaMap como fonte auxiliar, nunca prova exclusiva de precisão operacional;
4. World Port Index somente como seed/centroide/bounding box ampla, não como polígono operacional de berço;
5. derivação por histórico AIS usando H3 + densidade + DBSCAN, conforme metodologia UNECE AIS Berth Polygon Cookbook;
6. validação manual/visual e comparação contra line-up/eventos conhecidos.

Cada geofence deve preservar:

- `zone_id`;
- `port_id`;
- `terminal_id` quando aplicável;
- `zone_type`;
- `geometry`;
- `source_id`;
- `source_date`;
- `geofence_version`;
- `validation_status`;
- `confidence`;
- notas metodológicas.

### Zonas operacionais

- `SEA`
- `APPROACH`
- `ANCHORAGE`
- `CHANNEL` quando necessário
- `PORT`
- `BERTH`

`DEPARTED` é evento/estado derivado, não necessariamente uma geometria própria.

## 6. Tile38 — decisão final da V1

`Tile38` fica em `FUTURO`, não em runtime da V1.

Motivo: o worker atual já classifica posições contra geofences em processo antes da persistência. Introduzir Tile38 agora criaria novo serviço operacional sem ganho proporcional.

Critérios para promover Tile38:

- volume de AIS torna o geofencing em processo insuficiente;
- necessidade de eventos `enter/exit/cross` com baixa latência;
- múltiplos consumidores dependem dos mesmos eventos espaciais;
- necessidade de pub/sub geoespacial independente do worker AIS.

## 7. Port-call engine

O engine é próprio do AgroLog e não deve depender de um repositório externo como fonte de verdade.

Referências arquiteturais principais:

- `thanderoy/ais-tracker` — run-length/visitas em porto, geofence crossings, PostGIS e jobs idempotentes;
- `xang1234/neptune` — multi-source fusion, QC/provenance, port-call detection, streaming e replay;
- `UNECE/AIS` — geração/validação de polígonos de berço por AIS + H3 + DBSCAN;
- `Snaporaz6/ais-vessel-tracker` — reconstrução de port calls e histórico de posições.

### Eventos canônicos

- `APPROACH_STARTED`
- `PORT_ARRIVAL`
- `ANCHORAGE_ENTER`
- `ANCHORAGE_EXIT`
- `BERTH_ENTER`
- `BERTH_EXIT`
- `PORT_DEPARTURE`

Os eventos devem ser idempotentes e reproduzíveis a partir do histórico AIS + versão da geofence.

### Regras mínimas

- trânsito rápido por uma geofence não vira port call automaticamente;
- permanência mínima deve ser parametrizável por tipo de zona/porto;
- SOG, sequência temporal e posição anterior/posterior entram na classificação;
- gaps AIS são explicitamente registrados;
- evento reconstruído é `INFERIDO_A_PARTIR_DE_AIS` quando não houver confirmação portuária direta;
- atracação/realização oficial permanece separada da inferência AIS.

## 8. Reconciliação AIS × line-up

A implementação existente continua como núcleo.

Prioridade de identidade:

1. IMO exato;
2. MMSI exato;
3. nome normalizado/fuzzy somente como fallback;
4. porto, terminal, ETA e janela temporal para desempate.

Conflito de IMO/MMSI bloqueia fuzzy match.

### Estados externos

- `PROGRAMMED`
- `IN_TRANSIT`
- `APPROACHING`
- `ARRIVED_WAITING`
- `BERTHED`
- `DEPARTED_PENDING_REALIZED`
- `COMPLETED_REALIZED`

AIS de saída não confirma realizado.

### Métricas

- ETA informado × ATA observado/inferido;
- ETA revision count;
- waiting time;
- berth time;
- dwell time;
- line-up match rate;
- cancelamento/divergência;
- volume programado × realizado quando ambos forem observados;
- Line-up Reliability Score.

## 9. Fila e congestionamento

A fila da V1 deve ser derivada principalmente de navios em `ANCHORAGE`/`ARRIVED_WAITING` reconciliados ou classificados com confiança suficiente.

Indicadores iniciais:

- `vessels_waiting`;
- `potential_dwt_waiting` quando DWT vier de fonte autorizada/confiável;
- espera média;
- espera mediana;
- P90/P95;
- navios aproximando-se;
- taxa de atracação;
- tempo médio de berço;
- queue delta vs coleta anterior;
- queue percentile vs histórico;
- `VQI` — Vessel Queue Index;
- `Port Pressure Score`.

Nenhum índice deve ocultar os componentes observados que o formam.

## 10. ETA — estratégia V1

Não começar com deep learning.

### Baselines obrigatórios

1. ETA transmitido pelo próprio AIS;
2. ETA do line-up;
3. ETA cinemático simples com distância/velocidade;
4. ETA histórico por corredor/porto/tipo de navio.

### Primeiro modelo proprietário

Usar modelo tabular/tree-based antes de arquiteturas complexas, combinando:

- posição e distância ao porto;
- SOG/COG;
- ETA AIS;
- ETA line-up;
- histórico do navio/rota quando disponível;
- características da embarcação;
- horário/dia/sazonalidade;
- fila/congestionamento;
- clima/mar quando relevante;
- histórico de port calls.

Referências metodológicas incluem `cut-dicl/ais2eta` e pesquisas recentes que combinam port-call records + AIS e reportam melhora material frente ao ETA informado pelo navio.

Promoção de modelo exige validação temporal/out-of-sample e comparação direta contra todos os baselines.

## 11. Forecast de fila

Ordem de desenvolvimento:

1. nowcast reproduzível;
2. forecast 6h;
3. forecast 24h;
4. forecast 48h.

Features candidatas:

- fila atual;
- navios aproximando-se;
- ETA previsto;
- line-up 3/7/14 dias;
- taxa recente de atracação;
- berth occupancy;
- dwell/berth time;
- clima;
- restrições operacionais;
- sazonalidade;
- eventos excepcionais.

## 12. Histórico e replay

### V1

BigQuery permanece fonte histórica canônica.

Replay:

```text
BigQuery → API de janela temporal → compactação/amostragem → deck.gl TripsLayer
```

Não introduzir MobilityDB, Iceberg ou lakehouse apenas para habilitar replay.

### Escala futura

`PostGIS + MobilityDB` entra somente se BigQuery/API não atenderem latência, custo ou consultas espaço-temporais do produto.

`MobilityDB/MobilityLakehouse` fica como referência futura para trajetória nativa, TemporalParquet e pruning espaço-temporal em object storage.

## 13. Realtime

A V1 usa a infraestrutura AIS/WebSocket já existente e o Gateway/API do AgroLog.

Não introduzir nesta fase:

- Kafka;
- Redpanda;
- RisingWave;
- Redis geoespacial;
- Tile38;
- CDC distribuído.

Esses componentes só entram após medição objetiva de gargalo.

O frontend deve receber apenas deltas/posições necessárias, com rate limit e controle de frequência; não retransmitir histórico completo a cada atualização.

## 14. Fontes/cartografia náutica

S-57/S-101 é uma capacidade importante para aproximação, fundeadouro e berço quando houver dataset oficial/licenciado.

Projetos como `LarsSchy/SMAC-M` e `devladpopov/s57-parser` ficam `REFERENCIA` para ingestão/renderização de ENC. A V1 pode usar GDAL/OGR para conversão quando compatível com a licença da carta.

OpenSeaMap/OSM serve como camada auxiliar e de QA, não como autoridade definitiva de localização de berços.

## 15. Componentes que entram na V1

### CORE/uso imediato

- código AIS existente do AgroLog;
- BigQuery;
- contratos/reconciliação existentes;
- MapLibre;
- PMTiles para base estática quando aplicável;
- geofences versionadas;
- Gateway/API.

### POC para a própria V1

- `deck.gl` para alto volume e replay;
- H3 para densidade e geração/QA de geofences;
- método H3 + DBSCAN para berth polygons;
- Martin apenas se tiles dinâmicos forem necessários;
- Tippecanoe para geração de tiles;
- modelo ETA tabular proprietário após baselines.

### FUTURO, fora do runtime inicial

- Tile38;
- PostGIS;
- MobilityDB;
- Redpanda Connect;
- RisingWave;
- MobilityLakehouse;
- MLflow/Feast/Evidently/NannyML até existir modelo operacional suficiente.

### REFERÊNCIA, não dependência

- `thanderoy/ais-tracker`;
- `xang1234/neptune`;
- `UNECE/AIS`;
- `Snaporaz6/ais-vessel-tracker`;
- `cut-dicl/ais2eta`;
- AISdb;
- SMAC-M/S-57 parser;
- projetos acadêmicos de berth allocation/port simulation.

## 16. Critérios de aceite da V1

A V1 não é considerada pronta apenas porque o mapa abre.

Critérios:

1. cinco portos piloto geograficamente corretos;
2. geofences com fonte e versão;
3. pelo menos 95% dos eventos amostrados de chegada/atracação/saída coerentes com referências disponíveis;
4. line-up reconciliado sem promover programação a realizado;
5. histórico/replay reproduzível;
6. fila calculada de forma determinística;
7. source health visível;
8. data freshness visível;
9. ausência de segredo no frontend;
10. auditoria de identidade IMO/MMSI;
11. métricas de waiting/berth/ETA reproduzíveis;
12. UI permanece responsiva na carga-alvo definida para o piloto.

## 17. Decisão de congelamento

Após esta rodada, não realizar novas buscas amplas de ferramentas antes de construir a V1. Novas pesquisas devem ser específicas para um bloqueio real encontrado durante implementação ou validação.

A prioridade passa a ser execução: geofences corretas → port-call engine → AIS × line-up → API → MapLibre/deck.gl → replay → métricas → ETA/queue forecast.
