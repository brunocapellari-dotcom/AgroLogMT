# GitHub Research — AgroLog MT — 2026-09-28

## Objetivo

Nova rodada de pesquisa para identificar ferramentas e funcionalidades que agreguem capacidade real ao AgroLog MT sem duplicar fonte de verdade, orquestração, storage ou governança já existentes.

Critérios: aderência ao problema, manutenção atual, licença permissiva quando possível, segurança, integração com BigQuery/Cloud Run/MapLibre/Obsidian, ganho mensurável e estratégia de saída.

## Decisões

### ADOPT COMO POC — Pydantic AI + Pydantic AI Harness

**Papel:** runtime tipado para agentes analíticos e especializados do AgroLog.

Motivos:
- ferramentas e outputs tipados;
- capabilities compostas;
- Planning, SubAgents e Dynamic Workflow;
- Memory e Conversation Search para memória operacional segregada;
- Step Persistence e durable execution;
- instrumentação OpenTelemetry nativa;
- integração MCP e execução multi-modelo;
- evita instalar simultaneamente vários frameworks de agentes.

**Decisão arquitetural:** passa a ser o candidato preferencial para a primeira implementação dos agentes definidos em `contracts/ai_roles.v1.json`.

**LangGraph:** reclassificado para `REFERENCIA/ALTERNATIVA_CONDICIONAL`. Só deve ser promovido se um benchmark demonstrar requisito de grafo de estado/ciclos/controle explícito não atendido de forma adequada por Pydantic AI/Pydantic Graph/Harness.

Nenhum dos dois pode escrever diretamente no BigQuery fora do AgroLog Gateway ou promover conhecimento canônico sem auditoria.

### ADOPT COMO POC — Phoenix

**Papel:** observabilidade e avaliação do runtime de IA.

Usar para:
- tracing de chamadas de modelo e ferramentas;
- latência, tokens, custo e erros;
- datasets de avaliação;
- experimentos e regressão de prompts/agentes;
- RAG/retrieval eval;
- auditoria de tool calls.

Integração preferida via OpenTelemetry/OpenInference. Deve existir redaction/minimização de conteúdo sensível antes de produção.

Phoenix não substitui OpenTelemetry Collector nem os logs operacionais; é consumidor/especialização da telemetria de IA.

### ADOPT COMO POC — Promptfoo

**Papel:** regressão e red-team do comportamento de agentes/prompts/RAG.

Casos AgroLog:
- prompt/tool injection;
- exfiltração de dados;
- criação de claims sem evidência;
- quebra de classificação OBSERVADO/ESTIMADO/PROJETADO/INFERIDO;
- perda de qualifiers;
- uso de ferramenta não autorizada;
- regressões de resposta e de citação;
- comparação controlada entre modelos.

Promptfoo complementa, mas nunca substitui, unittest, contratos, testes live, data-quality gates e auditor final.

### ADOPT COMO POC — PySTAC Client + odc-stac

**Papel:** camada padrão de descoberta e carregamento de Earth Observation quando a fonte oferecer STAC.

Fluxo pretendido:

`STAC API → PySTAC Client → odc-stac/xarray → normalização/feature engineering → artefato/BigQuery`.

Aplicações:
- Sentinel/Landsat e derivados;
- umidade/vegetação/temperatura de superfície;
- chuva/sensoriamento remoto quando publicado por catálogo STAC;
- análise por AOI/município/região agrícola;
- construção de séries point-in-time.

Não substituir APIs oficiais simples quando elas já forem suficientes.

### ADOPT COMO POC — earthaccess + VirtualiZarr

**Papel:** acesso canônico a NASA Earthdata quando o produto estiver no ecossistema CMR/Earthdata.

Benefícios:
- busca, autenticação e acesso num mesmo cliente;
- download ou streaming;
- virtualização de NetCDF/HDF via VirtualiZarr sem duplicar arquivos grandes quando tecnicamente possível.

Aplicações-alvo: SMAP, GPM, MODIS/VIIRS e demais produtos NASA que forem aprovados no catálogo.

`Kerchunk` fica como `REFERENCIA/FALLBACK` para formatos/fluxos não atendidos pela virtualização preferencial.

### ADOPT COMO POC — STAC-GeoParquet

**Papel:** materializar metadados STAC em formato analítico bulk.

Uso:
- snapshot/versionamento de resultados de catálogo;
- consulta local com DuckDB/Polars;
- integração com GeoParquet e artefatos no GCS;
- reduzir milhões de requests/JSON para análise de inventário.

Não criar um catálogo paralelo ao Data Source Registry. O registry governa a fonte; STAC-GeoParquet é representação analítica de itens/assets.

### ADOPT COMO POC — TiTiler

**Papel:** tiles raster dinâmicos para o cockpit geográfico.

Complementa, sem substituir:
- MapLibre/deck.gl no frontend;
- PMTiles para vetor/estático;
- Martin para vector tiles dinâmicos.

Uso proposto:
- COG;
- STAC;
- Zarr/xarray;
- mapas de chuva, NDVI/EVI, temperatura, umidade e outros rasters.

Só entra no runtime quando existir uma camada raster que precise visualização dinâmica; antes disso, gerar artefatos estáticos continua mais simples.

### REFERENCE / BENCHMARK — Apache Hamilton

O projeto amadureceu para Apache Incubator e oferece DAGs Python testáveis, lineage e schema validation.

Decisão: não adicionar ao runtime agora. O AgroLog já possui SQLMesh/dlt/OpenLineage como caminhos preferenciais por responsabilidade. Hamilton pode ser benchmark para feature engineering Python complexa se os scripts atuais se tornarem difíceis de manter.

### POC DE ENGENHARIA — uv + Ruff

Objetivo:
- lock/reprodutibilidade;
- instalação mais rápida em runner efêmero;
- reduzir drift de ambiente;
- lint/format rápido.

Não migrar a release candidata atual no meio da homologação. Avaliar após o primeiro `FINAL RELEASE: PASS`, preservando `requirements*.txt` até equivalência reproduzível comprovada.

## Reafirmações

- HydroMT continua `FUTURO`, não é necessário para fechar ANA/HidroWeb.
- pgSTAC/stac-fastapi ficam `FUTURO/NAO_SELECIONADO AGORA`: exigiriam Postgres/PostGIS e criariam serviço adicional sem necessidade atual.
- Kerchunk é fallback/referência; VirtualiZarr é preferido quando integrado ao earthaccess.
- Apache Hamilton não substitui SQLMesh, dlt ou OpenLineage.
- Phoenix não substitui OpenTelemetry Collector.
- Promptfoo não substitui testes determinísticos nem auditoria de dados.
- LangGraph não será instalado em paralelo com Pydantic AI apenas por precaução.

## Ordem de execução

1. concluir PR #187 e o Full Project Final Gate;
2. implementar primeiro runtime mínimo de agente com Pydantic AI/Harness, sem acesso direto ao BigQuery;
3. instrumentar esse piloto com Phoenix/OpenTelemetry;
4. criar suíte Promptfoo sobre golden cases/ataques;
5. implementar um piloto Earth Observation com PySTAC Client + odc-stac ou earthaccess, escolhendo uma fonte real;
6. registrar os assets STAC em GeoParquet se o volume justificar;
7. adicionar TiTiler somente quando existir raster operacional a servir;
8. benchmark uv/Ruff no runner GCE após release homologada.

## Regra de promoção

Nenhuma ferramenta desta rodada vira CORE por documentação. Promoção exige teste executável com dado/caso real, licença revisada, segurança, benchmark e evidência de ganho.
