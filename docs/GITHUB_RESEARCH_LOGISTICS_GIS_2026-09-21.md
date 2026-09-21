# AgroLog MT — Pesquisa GitHub: Routing, GIS, AIS e Data Quality — 2026-09-21

## Regra de decisão

Nenhuma ferramenta entra por popularidade. Cada candidata é comparada contra o stack canônico por: aderência funcional, manutenção, licença, risco de segurança, duplicidade, custo operacional, facilidade de saída e benefício mensurável.

Classificações:
- **ADOPT** — entra no stack aprovado, ainda sujeito ao gate POC→CORE quando houver runtime.
- **REPLACE** — substitui uma ferramenta já selecionada na mesma função.
- **BENCHMARK** — referência/competidora de teste; não entra no runtime.
- **REJECT** — não entra no stack atual.

## Rodada solicitada

| Item | Decisão | Escopo AgroLog | Redundância resolvida |
|---|---|---|---|
| valhalla/valhalla | **ADOPT** | Engine preferencial para roteamento OSM, matriz OD, isócronas, rotas alternativas e map matching. MIT; ativo. | Valhalla passa a ser o candidato único para routing + map matching. FMM fica apenas como benchmark técnico se Valhalla falhar em requisito mensurável. OSRM permanece não selecionado. |
| PyVRP/PyVRP | **ADOPT** | Solver especializado para VRP, capacidade, janelas de tempo, múltiplos depósitos, pickup/delivery e frota. MIT; ativo. | PyVRP é o solver preferencial para VRP. OR-Tools permanece somente como otimizador geral, não como segundo solver VRP padrão. |
| gboeing/osmnx | **ADOPT** | Aquisição/modelagem/análise OSM, rede rodoviária, velocidades/tempos, conectividade e POIs para estudos locais/regionais e QA. MIT; ativo. | Não vira engine de roteamento de produção; prepara/analisa rede para Valhalla/AequilibraE. |
| M0r13n/pyais | **ADOPT** | Decoder/encoder NMEA AIVDM/AIVDO para receptores próprios, arquivos NMEA e fallback de baixo nível. MIT; ativo. | Não entra no caminho AISStream JSON atual; evita duplicar parsing já normalizado pelo fornecedor. |
| thanderoy/ais-tracker / PostGIS patterns | **ADOPT (patterns only)** | Reproduzir internamente port-call reconstruction, enter/exit, dwell, proximity, stay detection e jobs idempotentes usando contratos e dados AgroLog. | O repositório não é dependência: não possui licença explícita observada e sua arquitetura Postgres/PostGIS não substitui BigQuery. |
| uber/h3 + uber/h3-py | **ADOPT** | Grid espacial hierárquico canônico para densidade, corredores, QA geográfico, pressão logística e apoio a geofences AIS. Apache-2.0; ativo. | H3 é o único grid hierárquico padrão. Não adicionar S2/geohash como segundo grid sem caso objetivo. |
| sodadata/soda-core | **REJECT** | Não entra no runtime/contratos do AgroLog. | Duplica ODCS + Data Contract CLI + Pandera/CloudDQ e usa Elastic License 2.0. O AgroLog preserva contratos canônicos próprios/ODCS e qualidade BigQuery via CloudDQ/Dataplex. |

## Arquitetura terrestre após a comparação

Fluxo preferencial:

```
OSM PBF/Overpass
  -> PyOsmium (bulk) / OSMnx (estudo e QA)
  -> GeoParquet
  -> Valhalla
       -> rota
       -> matriz OD
       -> isócrona
       -> map matching
  -> AequilibraE (assignment/cenários)
  -> observações reais/frete
  -> PyVRP (VRP/frota)
```

Regras:
1. Valhalla não substitui AequilibraE: routing e assignment são funções distintas.
2. PyVRP não substitui Valhalla: otimização usa custos/matriz produzidos pela rede.
3. OSMnx não deve servir como routing service de produção.
4. OR-Tools fica restrito a otimização geral; PyVRP é o padrão para VRP.
5. FMM não fica como segundo map matcher padrão: apenas benchmark de contingência.

## Arquitetura marítima após a comparação

```
AISStream JSON -------------------------> adapter atual
NMEA/receptor próprio/arquivo ----------> pyais
                                         |
                                         v
                            normalização AIS canônica
                                         |
                            qualidade + geofence versionada
                                         |
                            port-call engine próprio
                      (patterns testados do ais-tracker)
                                         |
                               BigQuery canônico
```

BigQuery permanece fonte histórica analítica. PostGIS/MobilityDB só entra quando benchmark real demonstrar necessidade de baixa latência/transação espaço-temporal que BigQuery/API não atendam.

## Data contracts e qualidade

Stack canônico permanece:

```
JSON Schema/contratos AgroLog
  -> ODCS + Data Contract CLI
  -> validação Python/Pandera quando DataFrame fizer sentido
  -> CloudDQ/Dataplex no BigQuery
  -> source promotion gate
```

Soda Core não é adicionado porque criaria uma segunda linguagem/engine de contratos e de quality checks sem ganho comprovado, além do regime Elastic License 2.0.

## Nova rodada GitHub — candidatos adicionais

### osmcode/pyosmium — ADOPT

Bindings Python de libosmium, BSD-2-Clause, ativo. Candidato preferencial para leitura/filtragem **bulk** de PBF OSM (Brasil/América do Sul) sem depender de Overpass.

Uso:
- ingestão de PBF;
- filtros de ways/nodes/tags;
- geração de artefatos GeoParquet intermediários;
- preparação reprodutível da rede usada por Valhalla/QA.

Não substitui OSMnx: PyOsmium é bulk/baixo nível; OSMnx é análise/modelagem de rede.

### pyrosm/pyrosm — BENCHMARK

MIT e ativo. É mais conveniente para PBF→GeoDataFrame, mas se sobrepõe ao papel bulk do PyOsmium. Benchmark apenas em produtividade/performance antes de qualquer promoção.

### graphhopper/graphhopper — BENCHMARK

Apache-2.0, muito ativo e maduro. Excelente comparador externo de routing/matrix. Não entra junto com Valhalla no runtime; usar em benchmark de precisão, cobertura e performance.

### Project-OSRM/osrm-backend — REJECT

BSD-2-Clause e maduro, mas duplica routing já atribuído ao Valhalla e oferece menos alinhamento com o conjunto de recursos escolhido. Só reabrir se Valhalla falhar em requisito objetivo.

### VROOM-Project/vroom — REJECT

Bom solver C++ de VRP, mas duplica PyVRP no papel escolhido e adiciona serviço/runtime adicional. PyVRP permanece preferencial pela integração Python e adequação aos estudos do AgroLog.

### pgRouting/pgrouting — REJECT agora

GPL-2.0 e dependente do caminho PostGIS. Não há justificativa para introduzir PostGIS apenas para routing. Reavaliar somente se PostGIS entrar por necessidade transacional independente e houver um caso que Valhalla não resolva.

### duckdb/duckdb-spatial — ADOPT (POC local)

MIT, ativo e complementar ao DuckDB já selecionado. Pode acelerar QA espacial, GeoParquet, interseções e backfills locais sem criar serviço ou segunda fonte de verdade.

### OvertureMaps/overturemaps-py — BENCHMARK

MIT para a ferramenta; os datasets precisam de revisão própria de licença/termos. Útil como fonte secundária/QA para rede e entidades globais. Não substitui OSM como fonte principal de routing sem benchmark de cobertura e atualização.

### datacontract/datacontract-cli + bitol-io/ODCS — ADOPT / CONFIRMADO

Data Contract CLI (MIT) e ODCS (Apache-2.0) estão ativos e alinhados ao stack já escolhido. Permanecem canônicos; isso reforça a decisão de não adicionar Soda Core.

### GoogleCloudPlatform/cloud-data-quality — ADOPT / CONFIRMADO

Apache-2.0 e específico para BigQuery. Permanece o candidato de quality checks no warehouse, evitando trazer um segundo engine de qualidade.

### movingpandas/movingpandas — BENCHMARK

BSD-3-Clause, ativo. Benchmark offline para segmentação, stops e trajetória AIS. Não substitui o port-call engine próprio nem vira runtime sem ganho medido.

### apache/sedona — REJECT agora

Apache-2.0 e maduro, porém é plataforma distribuída adicional. Escala e complexidade não são justificadas enquanto BigQuery GIS + DuckDB Spatial + GeoParquet atendem.

## Testes obrigatórios antes de promoção

### Valhalla
- rotas MT→portos contra rotas conhecidas e malha oficial;
- matriz OD em lote;
- restrições de caminhão quando disponíveis;
- map matching com trilhas reais;
- latência, memória, tamanho de tiles e atualização OSM;
- comparação pontual com GraphHopper/OSRM sem manter ambos em produção.

### PyVRP
- VRP sintético + caso real de frota;
- capacidade, janela, múltiplos depósitos e pickup/delivery;
- estabilidade e tempo de solução;
- comparação com baseline OR-Tools apenas como benchmark.

### OSMnx / PyOsmium
- PBF MT e Brasil;
- conectividade/topologia;
- velocidades/tempos;
- reprodutibilidade e consumo de memória;
- comparação com rede Valhalla e dados DNIT/ANTT quando aplicável.

### pyais
- mensagens AIS tipos relevantes;
- multipart NMEA;
- mensagens inválidas/truncadas;
- round-trip encode/decode;
- equivalência com amostras de receptor e com normalização AgroLog.

### H3
- resoluções por caso de uso;
- estabilidade de agregações;
- custo/volume no BigQuery;
- bordas costeiras/geofences;
- conversão para GeoParquet/UI.

### Port-call patterns
- enter/exit idempotente;
- dwell parametrizado;
- gap AIS;
- trânsito rápido sem falso port call;
- proximidade ship-to-ship;
- reconstrução reproduzível por versão da geofence;
- comparação com line-up/ANTAQ/porto quando observado.

## Decisão consolidada

Novos componentes aprovados para o stack **sem ativação prematura de runtime**:
- Valhalla;
- PyVRP;
- OSMnx;
- PyOsmium;
- pyais;
- H3/H3-py;
- DuckDB Spatial;
- patterns de port-call do ais-tracker reproduzidos em código próprio.

Ferramentas mantidas apenas como benchmark/referência:
- GraphHopper;
- Pyrosm;
- Overture Maps;
- MovingPandas.

Não selecionadas no stack atual:
- Soda Core;
- OSRM;
- VROOM;
- pgRouting;
- Apache Sedona.

A prioridade continua sendo um único componente por função, benchmark antes de promoção e zero segunda fonte de verdade.
