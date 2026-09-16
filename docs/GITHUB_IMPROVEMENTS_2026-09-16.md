# GitHub / Tooling Research — 2026-09-16

## Objetivo

Pesquisar melhorias novas sem criar tool-sprawl. Toda decisão abaixo compara a lacuna com o stack canônico já existente. Nada aqui autoriza release parcial: qualquer adoção material continua subordinada ao Full Project Final Gate.

## Runners / CI sem tornar o repositório público

### `actions/runner` — ADOPT como opção de capacidade futura

Repositório oficial: `actions/runner`.

Release oficial observada nesta rodada: `v2.337.0`.

Uso potencial: self-hosted runner privado em infraestrutura controlada caso GitHub-hosted minutes continuem sendo gargalo recorrente.

Decisão atual: não provisionar ainda. O AgroLog já possui Cloud Shell/GCP operacional e agora possui `scripts/finalize_agrolog_without_actions.sh`, que reproduz o gate inteiro sem gastar GitHub-hosted Actions minutes. Um runner persistente adicionaria patching, hardening, disponibilidade, custo e superfície de ataque.

### `actions/actions-runner-controller` — REJECT por agora

É a solução oficial para escalar runners em Kubernetes. O AgroLog não precisa introduzir GKE/Kubernetes apenas para CI. Isso seria infraestrutura e custo operacional sem ganho proporcional no estágio atual.

### Tornar o repositório público — REJECT como workaround de minutos

O repositório contém arquitetura, contratos, infraestrutura, source registry e controles internos. Expor tudo publicamente apenas para ganhar minutos de runner aumenta superfície de ataque e é irreversível do ponto de vista de divulgação. A estratégia preferida é manter privado e executar gate via Cloud Shell/GCP ou, se necessário, self-hosted runner controlado.

## Supply chain / release tooling

### `aquasecurity/trivy` — KEEP / UPDATE PIN

Release observada nesta rodada: `v0.74.0`.

O zero-Actions finalizer usa essa versão e verifica o checksum oficial antes de executar scan de filesystem/IaC e das imagens de produção. Continua sendo o scanner principal; não adicionar OSV como segundo scanner obrigatório com responsabilidade sobreposta.

### `anchore/syft` — KEEP / UPDATE PIN

Release observada nesta rodada: `v1.51.1`.

O zero-Actions finalizer usa essa versão com checksum oficial para produzir SBOM SPDX do source e das imagens. Continua sendo a ferramenta canônica de inventário de componentes.

## Reprodutibilidade Python

### `astral-sh/uv` — POC / provável REPLACE

Release observada nesta rodada: `0.12.15`.

Objetivo: substituir a concatenação dinâmica de múltiplos `requirements*.txt` por resolução reprodutível com lock único e instalação mais rápida. O Cloud Shell atual já disponibiliza `uv`, portanto o POC não exige nova infraestrutura.

Critério de promoção: migração completa, `uv.lock` versionado, paridade de todas as dependências atuais, zero mudanças funcionais inesperadas e Full Project Final Gate integral verde. Não coexistir indefinidamente com outro mecanismo de lock.

## Testes

### `HypothesisWorks/hypothesis` — ADOPT direcionado após release corrente

Uso: property-based testing de parsers, normalizadores, natural keys, cardinalidade, datas, coordenadas, deduplicação e contratos de entrada externa.

Não substitui pytest; amplia pytest em pontos onde casos de borda gerados automaticamente agregam valor.

### `schemathesis/schemathesis` — ADOPT direcionado após Gateway homologado

Uso: testes generativos/contratuais do OpenAPI do AgroLog Gateway, incluindo payloads inválidos, limites e invariantes de resposta.

Não entra antes do Gateway real estar homologado, para evitar manter testes de API sobre uma superfície ainda não estável.

## Sensoriamento remoto, clima e dados globais

### `stac-utils/pystac-client` — ADOPT como cliente STAC canônico

Uso: descoberta e consulta padronizada de catálogos STAC para satélite/clima/agro, preservando provenance e point-in-time.

Evita clientes STAC caseiros por fonte. Adaptadores específicos ficam somente onde autenticação/licença exigir.

### `earthaccess-dev/earthaccess` — ADOPT para NASA Earthdata

Uso: busca/autenticação/acesso a produtos NASA Earthdata quando a camada de sensoriamento remoto avançar além dos endpoints já existentes.

Não substituir NASA POWER quando POWER for a fonte correta; `earthaccess` entra apenas para produtos Earthdata que não são cobertos pelo collector atual.

### `ecmwf/ecmwf-datastores-client` — POC para ECMWF/CDS

Uso potencial: ERA5/reanálises e outros produtos do Climate Data Store para climatologia, validação histórica, features de forecast e comparação com NOAA/CPTEC/INMET.

Preferir o cliente mais novo de datastores ao criar integração nova; `ecmwf/cdsapi` permanece referência/compatibilidade para endpoints que ainda o exijam. Nenhum produto ECMWF vira fonte operacional sem registrar licença, autenticação, frequência, freshness, custo e política de redistribuição no Data Source Registry.

### FAOSTAT — usar API oficial, não MCP comunitário como fonte canônica

A busca encontrou o namespace oficial `FAOSTAT` e implementações MCP comunitárias. Para o Global Supply & Demand, o AgroLog deve integrar a API/dataset oficial diretamente e tratar wrappers comunitários somente como referência de implementação. Isso evita dependência extra, mantém provenance primária e reduz risco de supply chain.

## Ferramentas mantidas como canônicas

- BigQuery, Cloud Run/Jobs, Cloud Build, Secret Manager e WIF continuam infraestrutura principal.
- Valhalla continua engine de routing; não adicionar OSRM concorrente.
- Pandera/CloudDQ continuam qualidade; não adicionar Great Expectations/Soda sem gap concreto.
- Trivy continua vulnerabilidade/IaC/imagens; não adicionar OSV como scanner principal duplicado.
- Gitleaks continua secrets; Zizmor + actionlint continuam GitHub Actions security/semantics.
- Syft continua SBOM.
- OpenLineage continua lineage.
- Docker/Cloud Build continuam builds; não adicionar plataforma de build paralela.
- Airflow, Prefect e Dagster continuam rejeitados enquanto Scheduler/Cloud Run/Data Source Registry cobrirem a necessidade.

## Prioridade imediata

1. Executar o zero-Actions finalizer sobre o head exato da branch de correção Cloud Build.
2. Obter `N6 CORE HOMOLOGATION: PASS`.
3. Obter `AGROLOG MT FINAL RELEASE: PASS` com zero skips.
4. Publicar/readback do status canônico `Whole project deterministic gate` no SHA testado.
5. Promover o head exato validado para `main`.
6. Aplicar/readback do ruleset de `main` usando o contexto canônico atual.
7. Depois da release real, migrar reprodutibilidade Python para `uv` e introduzir Hypothesis/Schemathesis/STAC/ECMWF de forma controlada, cada mudança sempre seguida pelo gate integral.
