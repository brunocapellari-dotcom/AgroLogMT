# Inteligência Pecuária — arquitetura integrada

## Estado canônico

Este documento descreve a versão integrada da Inteligência Pecuária no AgroLog MT. A existência de código no GitHub não autoriza declarar o domínio `PRODUCTION`.

Estado atual do candidato:

- código, contratos e testes determinísticos: implementados no candidato;
- quatro fontes operacionais: `GATED` no Data Source Registry;
- BigQuery, Cloud Run Job e Gateway: preparados para homologação pelo gate final global;
- promoção `gated -> active`: nunca automática; exige evidência e promoção formal;
- Replit/ambientes externos: não iniciados enquanto o candidato GitHub não estiver integralmente verde.

A Pecuária reutiliza a plataforma central do AgroLog: GitHub, Data Source Registry, collector compartilhado, armazenamento RAW, BigQuery, Cloud Run, AgroLog Gateway, segurança, observabilidade, auditoria e Segundo Cérebro. Não existe uma segunda infraestrutura de Pecuária.

## Princípios obrigatórios

1. BigQuery é a fonte única de verdade analítica.
2. GitHub guarda código, contratos, testes, workflows e documentação; bases RAW reais ficam fora do repositório.
3. Todo RAW preserva origem, hash, timestamp e referência de armazenamento.
4. `data_referencia`, `data_publicacao`, `data_coleta`, `competencia`, vintage e disponibilidade temporal são preservados quando aplicáveis.
5. Observado, derivado, inferido, estimado e projetado permanecem classes distintas.
6. Uma fonte não substitui outra apenas por medir conceito semelhante.
7. Fallback permanece outra evidência identificada, nunca relabeling silencioso.
8. Histórico sem disponibilidade/vintage comprovado não pode ser usado como feature point-in-time.
9. Fonte `planned`, `gated` ou `blocked` não vira produção por conveniência.
10. A aceitação é do projeto inteiro, nunca de um módulo isolado.
11. Runtime não cria datasets nem amplia IAM; datasets e grants são responsabilidade administrativa de bootstrap.
12. Toda consulta do Gateway usa o runtime BigQuery global com limite de bytes, timeout e erro controlado.

## Fontes implementadas

### IBGE PPM — estoque bovino municipal

`source_id`: `ibge_sidra_ppm_3939`

Uso:
- efetivo bovino municipal de Mato Grosso;
- histórico anual;
- concentração, crescimento e distribuição espacial do rebanho;
- base para cruzamentos futuros com pastagem, abate, preço, clima e logística.

Contrato temporal:
- observado realizado;
- `data_referencia` anual em 31/12;
- publicação histórica não é inventada;
- série histórica permanece inelegível como feature point-in-time até reconstrução verificável de vintages/publicações.

### IBGE Pesquisa Trimestral do Abate — fluxo oficial

`source_id`: `ibge_sidra_slaughter_1092`

Escopo fixado:
- tabela SIDRA 1092;
- variáveis 284 e 285;
- trimestre total;
- inspeção total;
- bovinos total;
- Mato Grosso.

Uso:
- cabeças abatidas;
- peso total de carcaças;
- peso médio de carcaça como métrica derivada;
- snapshots preservados para revisões.

A série continua protegida contra uso point-in-time enquanto a disponibilidade histórica de cada vintage não estiver comprovada.

### MAPA PGA/SIGSIF — snapshot SIF

`source_id`: `mapa_sigsif_slaughter_snapshot`

Uso:
- bovinos sob SIF por sexo e UF de procedência;
- composição macho/fêmea;
- cross-check atual do universo federal de inspeção.

Limite temporal obrigatório:
- o recurso oficial usado não contém competência interna do evento;
- atualização mensal do arquivo não autoriza reconstruir fluxo mensal retroativo;
- cada coleta é snapshot corrente observado;
- nunca somar automaticamente com a Pesquisa Trimestral do Abate.

### MDIC/SECEX Comex Stat — carne bovina

`source_id`: `mdic_comexstat_beef_mt_export_api`

Escopo corrente:
- exportação;
- Mato Grosso;
- carne bovina in natura NCM8 dos headings 0201/0202;
- miudezas explicitamente excluídas.

Escopo histórico:
- agregado robusto em HS4 0201/0202;
- detalhe NCM8 histórico exige mapping temporal observado;
- a cesta NCM8 atual não é retroprojetada cegamente;
- URF é unidade da Receita Federal, não porto físico.

## Relação das evidências

| Perspectiva | Fonte | Natureza |
|---|---|---|
| Estoque | IBGE PPM | rebanho anual municipal |
| Fluxo de abate | IBGE Abate | produção trimestral oficial |
| Composição SIF | MAPA SIGSIF | snapshot atual por sexo/procedência |
| Demanda externa | Comex Stat | exportação por produto/destino |

Nenhuma dessas fontes é fallback semântico das demais.

## Arquitetura operacional final

Fluxo:

`fonte -> Source Registry -> collector -> RAW/hash -> normalização -> BigQuery -> validação -> Gateway -> análise/modelo -> conhecimento/relatório`

### Data Source Registry

As quatro fontes existem como entradas concretas do domínio `cattle` e começam `gated`.

Canary de homologação:
- exige `AGROLOG_SOURCE_ID` individual;
- exige `AGROLOG_GATED_CANARY=1`;
- não pode ser acionado para o domínio inteiro;
- não altera o Registry versionado;
- não promove a fonte.

### BigQuery

Datasets:
- `pecuaria`: tabelas de estoque, abate e snapshot SIGSIF;
- `comercio_exterior`: dados e views de exportação.

O runtime usa `require_dataset`: collector não executa `CREATE SCHEMA` nem precisa de `bigquery.datasets.create`. O bootstrap administrativo cria os datasets e concede permissões mínimas.

Snapshots são imutáveis por hash, cargas são idempotentes e views latest preservam revisões sem sobrescrever a evidência bruta.

### Cloud Run

Job: `agrolog-pecuaria`.

Características:
- mesma imagem do collector AgroLog;
- `AGROLOG_REGISTRY_MODE=1`;
- `AGROLOG_DOMAIN=cattle`;
- nenhuma segunda camada de orquestração.

### AgroLog Gateway

O app de produção preserva o Gateway endurecido global e adiciona apenas o router Pecuária.

Rotas:
- `/v1/pecuaria/herd/state`;
- `/v1/pecuaria/herd/municipal`;
- `/v1/pecuaria/slaughter/quarterly`;
- `/v1/pecuaria/slaughter/sigsif/current`;
- `/v1/pecuaria/exports/beef`;
- `/v1/pecuaria/exports/beef/history`.

As rotas Pecuária não criam cliente BigQuery próprio. Reutilizam o runtime global, incluindo `maximum_bytes_billed`, timeout, cache e tratamento controlado de erros.

## Testes e autoridade de release

### Autoridade única

`.github/workflows/full-project-final-gate.yml`

O gate automático de PR valida o repositório inteiro: todos os testes determinísticos descobertos, compilação Python, contratos/configs, dependências, frontend, workflows, Zizmor, actionlint e Gitleaks.

O release final manual acrescenta scans de imagem/filesystem, SBOM, full-history secret scan, builds, GCP preflight, restore drill, testes LIVE, homologação N6 e auditor independente.

### Homologação N6 integrada

`scripts/homologate_n6_core.sh` é a sequência canônica. O release final não pode mais passar sem Pecuária.

A sequência integrada prova:
1. preflight de infraestrutura e segurança;
2. deploy único do collector compartilhado;
3. CONAB + idempotência;
4. Comex soja + idempotência;
5. quatro feeds Pecuária em canary gated, duas execuções por fonte e idempotência;
6. BigQuery Pecuária agregado;
7. view histórica bovina e semântica temporal;
8. deploy único do Gateway endurecido;
9. Gateway core;
10. Gateway Pecuária E2E;
11. restore e demais gates transversais pelo Full Project Final Gate.

`N6 CORE HOMOLOGATION: PASS` inclui explicitamente `pecuaria_feeds_gate`, `pecuaria_trade_history_gate` e `pecuaria_gateway_gate`.

### Workflow Pecuária

`.github/workflows/pecuaria-production.yml` é diagnóstico LIVE somente. Faz probes públicos de PPM, Abate, SIGSIF e Comex bovino, mas não possui caminho de deploy GCP nem autoridade de promoção.

Assim existe apenas uma autoridade de release e não há CI paralelo capaz de promover um módulo isoladamente.

## Pesquisa GitHub e decisões de ferramentas

### Selecionado para próxima expansão: MapBiomas + Google Earth Engine API

Fontes/repositórios de referência:
- `mapbiomas-brazil/user-toolkit` — ferramenta pública oficial do MapBiomas Brasil;
- `google/earthengine-api` — cliente oficial do Google Earth Engine.

Dados prioritários:
- classe Pastagem do MapBiomas Cobertura 30 m;
- Condição de Vigor da Pastagem, Coleção 11, 2000–2025;
- transições de vigor calculadas sobre a série oficial;
- futuramente idade, mudança de área e produtos de produtividade/biomassa quando o contrato oficial estiver validado.

Asset oficial já identificado para vigor:
`projects/mapbiomas-public/assets/brazil/lulc/collection11/mapbiomas_brazil_collection11_pasture_vigor_v1`.

Aplicações futuras:
- hectares de pastagem municipal;
- rebanho/ha implícito;
- pressão animal;
- mudança de área;
- condição/vigor;
- capacidade de suporte como contexto analítico, nunca como diagnóstico isolado.

Não será criado collector vazio nesta versão. A integração só entra no próximo release candidato quando conta/autorização GEE, contrato de asset, licença, exportação, RAW/proveniência, BigQuery, testes e gate E2E puderem ser entregues juntos.

### Selecionado para investigação: WOAH WAHIS

A WAHIS é referência oficial global para notificações e monitoramento de doenças animais. É candidata para risco sanitário, comércio e eventos de febre aftosa e outras doenças relevantes.

Não entra ainda no Registry executável porque o contrato machine-readable/API/download ainda precisa ser validado. A próxima implementação só ocorrerá com endpoint, termos, grain, temporalidade e método de coleta definidos.

### Reutilizar antes de criar novo conector: USDA FAS

O AgroLog já possui infraestrutura USDA FAS/PSD. Para mercado global de bovinos/carne, a prioridade é estender/reutilizar essa stack em vez de criar uma segunda integração USDA.

### Base dos Dados

`basedosdados/sdk` fica como fonte secundária de QA, descoberta e reconciliação. Não substitui IBGE, MAPA, MDIC ou outra fonte primária oficial na verdade canônica.

### Não adotar agora: Pandera / Great Expectations

Ambos podem oferecer validação de dados, mas o AgroLog já possui contratos por fonte, quality gates, tie-out, BigQuery validators e gate global. Adicioná-los agora criaria uma segunda camada de validação sem eliminar responsabilidade existente.

Reavaliar apenas se houver ganho demonstrável em vários domínios e redução líquida de código/manutenção.

### Não adotar agora: PySTAC Client

`stac-utils/pystac-client` é uma boa ferramenta quando houver catálogos STAC relevantes. Para a primeira expansão MapBiomas, o GEE oficial já fornece o caminho canônico; adicionar STAC agora seria tool-sprawl.

### dbt / SQLMesh / dlt

Continuam como POCs condicionais, não migração transversal. Só entram quando um fluxo real provar redução material de boilerplate, versionamento/lineage ou custo de manutenção sem duplicar loaders homologados.

### OpenLineage

Permanece candidato incremental para lineage. Não é blocker da Pecuária atual porque provenance/hash/snapshot já são preservados; eventual adoção deve transportar essa evidência, não criar uma segunda fonte de verdade.

## Próxima expansão de dados

Após o candidato atual completar o gate integral:

1. MapBiomas Pastagem + Vigor via Earth Engine oficial;
2. preços físicos/indicadores autorizados IMEA e CEPEA após termos/licença definidos;
3. B3 futuro de boi quando contrato e fonte oficial estiverem definidos;
4. plantas frigoríficas, habilitações e capacidade por fonte oficial;
5. GTA/INDEA-MT somente com acesso legal e autorizado;
6. WOAH WAHIS para risco sanitário após validar interface machine-readable;
7. USDA FAS cattle/beef reutilizando o conector existente;
8. milho, farelo, clima, pastagem e logística como drivers externos.

## Camada N6 Pecuária

Somente com dados e vintages adequados:
- ciclo pecuário;
- retenção/descarte de fêmeas;
- disponibilidade futura de animais;
- pressão de abate;
- peso médio de carcaça;
- estoque x abate;
- exportação x produção;
- preço/basis;
- pastagem/lotação implícita;
- custos de alimentação;
- risco sanitário, climático e logístico.

Modelos seguem o padrão N6: walk-forward, point-in-time, baselines simples, controle de leakage, incerteza/calibração, estabilidade temporal e evidência fora da amostra.

## Google Cloud, Replit e Claude Code

### Google Cloud

Arquitetura preparada:
- BigQuery: verdade analítica;
- Cloud Run Jobs: collectors;
- Cloud Run Service: Gateway;
- Artifact Registry: imagens;
- WIF/OIDC: CI/CD sem chave JSON;
- RAW externo com hash/proveniência;
- bootstrap/IAM separado de deploy recorrente.

O preflight global exige o dataset `pecuaria` e observa o job `agrolog-pecuaria`.

### Claude Code

Claude Code consome o mesmo GitHub, `CLAUDE.md`, contratos e gates. Não deve criar cópia divergente do projeto.

### Replit

Replit será ambiente de desenvolvimento, não fonte de verdade. Sua integração só começa após o candidato GitHub estar integralmente verde.

Regras:
- clonar/importar o GitHub canônico;
- secrets apenas no secret store;
- nenhuma chave GCP estática versionada;
- recursos de desenvolvimento/homologação por padrão;
- código válido retorna ao GitHub;
- nenhum artefato apenas do Replit é promovido sem commit e gate canônico.

## Critério de conclusão

A Inteligência Pecuária só é operacional quando, no mesmo release candidato:

- Full Project Final Gate = PASS;
- probes LIVE = PASS;
- datasets/IAM/preflight = PASS;
- quatro fontes canary carregadas e idempotentes;
- RAW/proveniência presentes;
- BigQuery e visão histórica bovina validados;
- Gateway core e Pecuária E2E validados;
- restore, segurança, lineage/proveniência e observabilidade aplicáveis em PASS;
- promoção de fonte formalmente evidenciada;
- nenhum teste obrigatório pulado.

Até essa evidência existir, o estado correto é `GATED`.
