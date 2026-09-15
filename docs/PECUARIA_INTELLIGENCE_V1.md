# Inteligência Pecuária — Arquitetura Operacional V1

## Missão

A Inteligência Pecuária é um domínio operacional separado do relatório agrícola/logístico principal do AgroLog MT. Ela compartilha infraestrutura canônica — GitHub, BigQuery, RAW/Drive, AgroLog Gateway, observabilidade e Segundo Cérebro — sem misturar conteúdo pecuário no relatório agrícola principal.

A V1 não é um protótipo descartável. O fluxo alvo é ponta a ponta:

`fonte oficial/autorizada → RAW imutável → normalização → qualidade/linhagem → BigQuery → views analíticas → AgroLog Gateway → agentes/BI/Segundo Cérebro → validação previsto × realizado`

## Fontes de verdade

- **GitHub** — código, contratos, schemas, testes, workflows e documentação.
- **BigQuery** — verdade analítica estruturada.
- **Drive/GCS RAW** — artefatos originais e evidências.
- **AgroLog Gateway** — única camada de exposição controlada para consultas e agentes.
- **Obsidian/Segundo Cérebro** — conhecimento técnico, contexto, relações causais e sínteses; não substitui os dados canônicos.

## Fontes implementadas

### IBGE PPM — rebanho bovino municipal

- tabela SIDRA 3939;
- efetivo bovino por município de Mato Grosso;
- histórico desde 1974 quando disponível na fonte;
- `data_referencia = 31/12` do ano da PPM;
- `data_publicacao` histórica não é inventada;
- registros históricos permanecem `point_in_time_feature_eligible=false` até reconstrução documental de disponibilidade/vintage;
- snapshot RAW preservado;
- carga idempotente por `snapshot_id + record_id`;
- views municipal/latest e agregado estadual por ano;
- auditoria de carga e tie-out exato.

### MDIC/SECEX Comex Stat — carne bovina in natura

Dois usos deliberadamente distintos:

1. **Operação corrente mensal** — usa os NCM8 correntes do contrato `product_trade_codes.v1.json` para 0201/0202, MT, exportação, sem miudezas.
2. **Histórico analítico 1997+** — usa headings HS4 `0201` e `0202` sobre a tabela canônica `comexstat_ncm_export`. Isso mantém o agregado completo mesmo quando os subcódigos NCM8 mudam.

Regras:

- `0201` → fresca/refrigerada;
- `0202` → congelada;
- miudezas `0206` permanecem fora do agregado;
- qualquer análise histórica por NCM8 específico continua exigindo correlação temporal válida;
- `SG_UF_NCM` representa a UF declarada do produto no módulo NCM;
- URF é unidade da Receita Federal e não deve ser tratada automaticamente como porto físico;
- kg, toneladas, FOB e USD/t são preservados/derivados com rastreabilidade.

## BigQuery

Dataset próprio: `pecuaria`.

Objetos principais:

- `pecuaria.ibge_ppm_cattle_mt`;
- `pecuaria.v_ibge_ppm_cattle_mt_latest`;
- `pecuaria.v_ibge_ppm_cattle_mt_state_year`;
- `comercio_exterior.v_pecuaria_mt_beef_exports` — view derivada da tabela Comex canônica, sem segunda ingestão histórica.

O histórico Comex continua no dataset canônico `comercio_exterior`; a Pecuária cria apenas a interpretação controlada do domínio.

## AgroLog Gateway

Rotas somente leitura:

- `GET /v1/pecuaria/herd/state`;
- `GET /v1/pecuaria/herd/municipal`;
- `GET /v1/pecuaria/exports/beef`.

Regras:

- parâmetros validados;
- queries parametrizadas;
- sem exposição direta do BigQuery ao consumidor;
- escopo NCM corrente lido do contrato canônico;
- avisos temporais e semânticos retornados junto aos dados;
- autenticação e IAM continuam governados pelo bootstrap central do Gateway.

## Automação e produção

### Cloud Run

Job dedicado lógico: `agrolog-pecuaria`.

Ele reutiliza:

- mesma imagem/código de coleta do AgroLog;
- mesma service account do coletor;
- mesmo RAW/Drive;
- mesmos manifestos e observabilidade;
- dataset pecuário próprio para isolamento analítico.

### GitHub Actions

`pecuaria-production.yml`:

- mudanças na `main` relacionadas ao domínio → deploy do coletor Pecuária, homologação completa, deploy/tie-out da view histórica, deploy do Gateway e teste E2E;
- execução mensal → roda coleta corrente e toda a regressão operacional;
- autenticação por Workload Identity Federation, sem chave JSON;
- concorrência bloqueada para impedir dois ciclos produtivos simultâneos.

## Bootstrap administrativo

O deploy recorrente não recebe privilégio para criar datasets ou IAM.

Uma única preparação administrativa cria/valida o dataset `pecuaria` e concede:

- `agrolog-collector`: `roles/bigquery.dataEditor` no dataset pecuário;
- `agrolog-gateway`: `roles/bigquery.dataViewer` em `pecuaria` e `comercio_exterior`.

Depois disso, rotina de deploy e coleta não exige privilégio administrativo.

## Testes e gates

A política é regressão de **100% do projeto**, não apenas testes locais do módulo.

A suíte global executa:

- todos os `unittest` existentes;
- testes PPM;
- testes BigQuery/PIT/idempotência;
- contrato NCM/HS4;
- queries do Gateway;
- configs de produção;
- compilação dos módulos Python relevantes;
- validação de YAML;
- validação de JSON;
- sintaxe dos scripts shell;
- harness sintético N6;
- build completo da Maritime UI.

Gates live adicionais:

- PPM SIDRA atual e histórico;
- auditoria observada de subcódigos Comex;
- carga BigQuery real;
- reexecução idempotente;
- tie-out da view histórica HS4 contra a tabela Comex canônica;
- chamadas autenticadas ao Gateway.

## Regras temporais

- dado realizado não vira feature point-in-time apenas porque existe hoje;
- `data_referencia`, `data_publicacao`, `data_coleta` e `competencia` permanecem conceitos distintos;
- backtests usam apenas informação cuja disponibilidade no corte tenha sido comprovada;
- revisões de fonte são preservadas via snapshots quando aplicável;
- previsão deve ser persistida antes do realizado para avaliação honesta.

## Radar GitHub — melhorias avaliadas em 15/09/2026

### rOpenSci/rnassqs — REFERÊNCIA / alta prioridade futura

Uso: padrão maduro para consultar USDA NASS QuickStats e construir benchmark internacional de rebanho, vacas, bezerros, produção e indicadores correlatos dos EUA.

Aproveitar conceitos:

- descoberta programática de parâmetros;
- consultas reproduzíveis;
- validação de filtros antes de grandes downloads;
- separação entre aquisição e análise.

Não introduzir dependência R no runtime apenas para copiar a API; implementar adapter Python próprio sobre a fonte oficial quando a frente internacional entrar.

### USDA-REE-ERS/ARMS-Data-API — FONTE/REFERÊNCIA futura

Uso: custos, estrutura econômica, produtividade e características de operações agropecuárias dos EUA, incluindo especialização em cattle.

Valor: ajuda a separar sinal físico de rebanho de sinal econômico de margem/custo e fornece benchmark internacional de estrutura produtiva.

### USDA LMPRS + cbw1243/usdampr — FONTE prioritária internacional / código apenas referência

Uso: preços obrigatórios reportados de bovinos, carne e transações no mercado dos EUA.

Regra: priorizar a API oficial USDA AMS/LMPRS. O pacote `usdampr` serve como referência de contrato, histórico e tratamento; não deve se tornar dependência central sem necessidade.

### mapbiomas/brazil-pasture — alta prioridade nacional

Uso: metodologia e produtos para mapear área e dinâmica de pastagens com Landsat/Sentinel.

Aplicações Pecuária:

- área de pastagem por município/região;
- conversão/recuperação/degradação quando suportada pelo produto oficial;
- pressão `rebanho / área de pastagem`;
- cruzamento com seca, NDVI/EVI, chuva e produtividade forrageira;
- explicação espacial de retenção/abate e capacidade de suporte.

Os produtos oficiais/metodologia são a fonte; o repositório é referência de implementação, não justificativa para copiar assets ou código sem revisão de licença.

### digivet-consortium/movenet / movenetapp — REFERÊNCIA metodológica

Uso futuro quando GTA/movimentação autorizada estiver estruturada.

Conceitos úteis:

- padronização de diferentes layouts de movimentação;
- pseudonimização;
- geração de redes origem-destino;
- centralidade, comunidades e hubs;
- integração com modelos de transmissão sanitária;
- avaliação do impacto de anonimização nas métricas de rede.

O AgroLog deve implementar os conceitos sobre os próprios contratos e dados autorizados, sem necessidade de incorporar a interface Shiny.

### Repositórios genéricos de previsão de preço de gado

Não promovidos. Os candidatos encontrados têm baixa evidência de manutenção, metodologia, validação fora da amostra e prevenção de leakage. Modelos proprietários devem ser treinados sobre datasets point-in-time do AgroLog e comparados com benchmarks simples antes de qualquer promoção.

## Melhorias aprovadas para a próxima expansão

1. **Abate e oferta física** — integrar IBGE Pesquisa Trimestral do Abate e fontes oficiais de inspeção/frigoríficos, preservando metodologia e revisões.
2. **Preços físicos e futuros** — CEPEA/IMEA/B3 e fontes privadas autorizadas; preço spot, diferencial regional, basis e curva futura separados.
3. **Movimentação animal** — GTA/INDEA autorizada, com resolução de entidades, OD e rede de movimentações.
4. **Pastagens** — MapBiomas + clima/sensoriamento remoto para área, condição e pressão animal.
5. **Frigoríficos** — cadastro/capacidade/status de plantas, habilitações de exportação e raio de competição por boi.
6. **Mercado internacional** — USDA NASS, AMS LMPRS, ERS/ARMS e comércio exterior dos principais concorrentes.
7. **Sanidade** — eventos oficiais somente como variável de risco/fluxo e, quando relevante, driver externo de demanda/oferta.
8. **Modelos N6** — ciclo pecuário, retenção/abate, disponibilidade de animais, preço/basis e exportação; promoção apenas com point-in-time, walk-forward, calibração e estabilidade de regime.

## Critério de versão operacional

A V1 só é considerada operacional quando todos os itens abaixo forem comprovados no ambiente real:

- bootstrap GCP concluído;
- job `agrolog-pecuaria` implantado;
- PPM carregada e reexecutada idempotentemente;
- Comex corrente carregado/reexecutado;
- view histórica 0201/0202 criada e reconciliada;
- Gateway implantado e as três rotas aprovadas em E2E;
- suíte global verde;
- live probes sem quebra material de contrato;
- evidências registradas em GitHub Actions/BigQuery.
