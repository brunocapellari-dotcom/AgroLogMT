# Geopolitical Watch — Reports e Noticias

## Objetivo

Este documento define a camada editorial e analitica dos reports do Geopolitical Watch. A arquitetura-base e a governanca geral permanecem em `docs/GEOPOLITICAL_WATCH.md` e `docs/DATA_GOVERNANCE.md`.

A partir da versao `geo-report-v0.2`, noticias deixam de ser apenas insumo de score e passam a integrar explicitamente cada report.

## Estrutura do report

Cada evento selecionado deve conter:

- titulo e identificador canonico do cluster;
- prioridade de triagem `0-100`;
- nivel de verificacao;
- status de corroboracao;
- data de referencia;
- pais/regiao quando sustentados pela fonte;
- atores e fatalidades quando fornecidos por fonte codificada;
- areas de impacto AgroLog, sempre marcadas como inferidas enquanto nao houver validacao causal posterior;
- evidencia codificada/curada;
- bloco `Noticias relacionadas`;
- bloco `O que observar`.

## Noticias relacionadas

Cada noticia preserva no minimo:

- manchete;
- publicador/veiculo inferido pelo dominio da URL;
- data/hora de publicacao quando disponivel;
- URL original;
- `source_id` do coletor/agregador;
- nivel de verificacao.

Regra central: o fato observado e a existencia da publicacao capturada. Uma noticia isolada nao confirma automaticamente o acontecimento descrito.

### Corroboracao

A corroboracao editorial usa publicadores independentes, nao apenas IDs tecnicos de coletores.

Isso impede que duas consultas diferentes ao mesmo agregador contem como duas fontes independentes quando ambas apontam para o mesmo veiculo.

Estados iniciais:

- `single_publisher_osint` — um unico publicador;
- `multi_publisher_osint` — dois ou mais publicadores distintos;
- `curated_report` — relatorio institucional/curado;
- `curated_and_corroborated` — relatorio curado com fonte adicional;
- `research_coded` — evento presente em base de pesquisa codificada.

## Formatos

O runner local gera simultaneamente:

```text
.agrolog/reports/geopolitical/YYYY-MM-DD/<timestamp>.json
.agrolog/reports/geopolitical/YYYY-MM-DD/<timestamp>.md
.agrolog/reports/geopolitical/latest.json
.agrolog/reports/geopolitical/latest.md
```

O JSON e o contrato estruturado para API, BigQuery, dashboard e agentes. O Markdown e a versao humana/editorial.

## Fontes

### GDELT DOC 2.0

Permanece como radar noticioso de alta frequencia. O DOC 2.0 entrega lista de artigos e metadados de cobertura; o AgroLog preserva link e horario observavel e trata os itens como `osint_signal`.

### ReliefWeb

Foi implementado parser para reports humanitarios/institucionais, classificados como `curated_report`.

A fonte fica desabilitada por padrao porque, desde 01/11/2025, a API exige `appname` pre-aprovado. O identificador deve ser fornecido no ambiente como:

```text
RELIEFWEB_APPNAME=<appname-aprovado>
```

O GitHub nao deve armazenar esse valor na configuracao.

### UCDP

Permanece preparado e desabilitado ate a conclusao de paginacao, janela temporal dinamica e provisionamento de token.

## BigQuery

O modulo `collector/geopolitical_bigquery.py` cria sob demanda o dataset definido por `AGROLOG_INTELLIGENCE_DATASET` (default `agrolog_intelligence`) e tres tabelas:

- `geopolitical_events`;
- `geopolitical_clusters`;
- `geopolitical_reports`.

Eventos e clusters usam IDs deterministas e operacoes `MERGE` para permitir reprocessamento sem multiplicacao silenciosa.

O payload completo e preservado como JSON enquanto campos centrais sao materializados para particionamento e consulta. Isso permite evoluir o contrato sem perder a evidencia original normalizada.

## Runner de nuvem

`collector.geopolitical_cloud_runner` usa:

```text
fonte
  -> CollectorEngine.run_source_capture()
  -> RAW no Drive
  -> manifest/state no BigQuery operacional
  -> parser/normalizacao
  -> geopolitical_events
  -> clustering
  -> geopolitical_clusters
  -> report JSON + Markdown
  -> geopolitical_reports
```

Variaveis principais:

```text
AGROLOG_GEOPOLITICAL_CONFIG=/app/collector/config/sources.geopolitical.example.json
AGROLOG_INTELLIGENCE_DATASET=agrolog_intelligence
AGROLOG_GEO_REPORT_MIN_PRIORITY=0
AGROLOG_GEO_REPORT_MAX_EVENTS=20
AGROLOG_GEO_REPORT_MAX_NEWS=5
```

O runner reutiliza `DriveBigQueryStore`, portanto tambem exige as variaveis ja usadas pelos coletores de nuvem, incluindo projeto GCP, localizacao BigQuery e pasta RAW no Drive.

## Frequencia recomendada

- GDELT/noticias: horario;
- ReliefWeb: horario quando habilitado;
- UCDP: diario depois de concluir a integracao;
- report situacional: a cada ciclo horario, preservando historico no BigQuery;
- promocao para report AgroLog principal: somente quando houver elo causal material para agro/logistica.

## Integracao com reports AgroLog

Quando um evento tiver impacto AgroLog plausivel, o report principal deve receber um bloco curto, sem transformar o produto em clipping geral de guerra.

Formato editorial recomendado:

```text
Geopolitica e risco logistico
- Evento: o que aconteceu / o que esta confirmado
- Impacto potencial: energia, fertilizantes, shipping, comercio ou logistica
- Noticias: 2-5 links mais relevantes e independentes
- O que observar: variaveis que confirmariam ou rejeitariam o impacto
```

Eventos sem elo material permanecem apenas no Geopolitical Watch.

## Testes

O workflow `.github/workflows/test-geopolitical-watch.yml` executa os testes do monitor e dos reports em pull requests que alterem essa camada.
