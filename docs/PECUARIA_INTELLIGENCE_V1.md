# Inteligência Pecuária — arquitetura integrada

## Status desta versão

Esta documentação descreve o candidato integrado da Inteligência Pecuária dentro do AgroLog MT. O domínio não é declarado `PRODUCTION` apenas porque os componentes existem no GitHub.

Estados válidos nesta fase:

- código/contratos/testes determinísticos: implementados;
- fontes reais: `GATED` no Data Source Registry até canary + homologação GCP + promoção formal;
- BigQuery/Cloud Run/Gateway: preparados para homologação real;
- promoção para `active`: somente após evidência do gate de fonte e do Full Project Final Gate.

O domínio Pecuária permanece sob o AgroLog MT e usa os mesmos serviços compartilhados: GitHub, Data Source Registry, Cloud Run, BigQuery, armazenamento RAW, AgroLog Gateway, observabilidade, segurança, auditoria e Segundo Cérebro.

## Princípios obrigatórios

1. BigQuery é a fonte única de verdade analítica.
2. GitHub guarda código, contratos, SQL, testes, workflows e documentação — nunca bases RAW reais.
3. Todo artefato RAW deve preservar origem, hash, timestamp e referência de armazenamento.
4. `data_referencia`, `data_publicacao`, `data_coleta`, `competencia`, vintage e disponibilidade temporal são preservados quando aplicáveis.
5. Dado observado, cálculo derivado, inferência, estimativa e projeção não podem ser confundidos.
6. Uma fonte não substitui outra apenas porque mede conceito parecido.
7. Fallback é outra evidência identificada, nunca relabeling silencioso.
8. Histórico sem disponibilidade/vintage comprovado não pode ser usado como feature point-in-time.
9. Nenhuma fonte `planned`, `gated` ou `blocked` vira produção por conveniência.
10. A aceitação é do projeto inteiro, não do módulo isolado.

## Fontes Pecuária implementadas

### 1. IBGE PPM — estoque bovino municipal

`source_id`: `ibge_sidra_ppm_3939`

Uso:
- efetivo bovino municipal em Mato Grosso;
- histórico anual;
- base para distribuição espacial do rebanho, concentração, crescimento e relação futura com pastagem, abate, preços e logística.

Contrato temporal:
- observado realizado;
- `data_referencia` anual em 31/12;
- publicação histórica não é inventada;
- histórico permanece inelegível como feature point-in-time até reconstrução verificável dos vintages/publicações.

### 2. IBGE Pesquisa Trimestral do Abate — fluxo oficial

`source_id`: `ibge_sidra_slaughter_1092`

Uso:
- bovinos abatidos em MT;
- peso total de carcaças;
- cálculo derivado de peso médio de carcaça;
- histórico trimestral revisionável por snapshot.

Escopo SIDRA fixado:
- tabela 1092;
- variáveis 284 e 285;
- trimestre total;
- inspeção total;
- bovinos total.

Peso médio é derivado, não observado bruto.

### 3. MAPA PGA/SIGSIF — snapshot SIF

`source_id`: `mapa_sigsif_slaughter_snapshot`

Uso:
- abate sob SIF por sexo e UF de procedência;
- composição macho/fêmea;
- cross-check do ambiente federal de inspeção;
- sinal para retenção/descarte de fêmeas quando metodologicamente aplicável.

Limite temporal obrigatório:
- o CSV oficial utilizado não contém competência/data interna da observação;
- a atualização mensal do arquivo não autoriza reconstruir uma série mensal retroativa;
- cada coleta é tratada como snapshot corrente do universo SIF;
- nunca somar automaticamente com a Pesquisa Trimestral do Abate.

### 4. MDIC/SECEX Comex Stat — carne bovina

`source_id`: `mdic_comexstat_beef_mt_export_api`

Escopo corrente:
- exportação;
- Mato Grosso;
- carne bovina in natura NCM8 de 0201/0202;
- miudezas explicitamente excluídas.

Escopo histórico:
- agregado robusto em HS4 0201/0202;
- detalhe NCM8 histórico exige mapping temporal observado antes de qualquer afirmação retroativa;
- URF continua sendo unidade da Receita Federal, não porto físico.

## Relação entre as quatro perspectivas

As fontes são complementares e não intercambiáveis:

| Perspectiva | Fonte | Natureza |
|---|---|---|
| Estoque | IBGE PPM | rebanho anual municipal |
| Fluxo de abate | IBGE Abate | produção trimestral oficial |
| Composição SIF | MAPA SIGSIF | snapshot corrente por sexo/procedência |
| Demanda externa | Comex Stat | exportação por produto/destino |

Nenhuma delas foi configurada como fallback semântico de outra no Registry.

## Arquitetura operacional

Fluxo canônico:

`fonte → Source Registry → collector → RAW/hash → normalização → BigQuery → validação → Gateway → análise/modelo → conhecimento/relatório`

### Data Source Registry

As quatro fontes Pecuária existem como entradas concretas do domínio `cattle`.

Estado inicial: `gated`.

O job normal `agrolog-pecuaria` roda em Registry Mode e não executa fontes gated. Para homologação existe um canary explícito:

- exige `AGROLOG_SOURCE_ID` individual;
- exige `AGROLOG_GATED_CANARY=1`;
- não funciona para um domínio inteiro;
- não muda o status versionado do Registry;
- não promove automaticamente a fonte.

Essa separação evita o ciclo incorreto de ativar uma fonte antes de prová-la.

### BigQuery

Dataset principal:

`pecuaria`

Dataset de comércio exterior compartilhado:

`comercio_exterior`

Objetos principais do domínio são criados sob demanda pelos loaders homologados. Snapshots são idempotentes e preservam revisões; chaves naturais não são consideradas globalmente únicas entre snapshots.

### Cloud Run

Job:

`agrolog-pecuaria`

Modo:

- `AGROLOG_REGISTRY_MODE=1`;
- `AGROLOG_DOMAIN=cattle`;
- mesma imagem e runtime compartilhados do collector AgroLog;
- sem segundo orquestrador.

### AgroLog Gateway

O Gateway preserva o app endurecido global e registra o router Pecuária por composição em `gateway.production_app`.

Rotas do domínio:

- `/v1/pecuaria/herd/state`;
- `/v1/pecuaria/herd/municipal`;
- `/v1/pecuaria/slaughter`;
- `/v1/pecuaria/sigsif/current`;
- `/v1/pecuaria/exports/beef`;
- `/v1/pecuaria/exports/beef/history`.

O Gateway continua privado, non-root, com identidade própria, limites de BigQuery e sem acesso direto do usuário final ao banco.

## Teste e promoção

### Gate determinístico

Autoridade única:

`.github/workflows/full-project-final-gate.yml`

Ele valida o repositório inteiro, incluindo:
- todos os testes Python descobertos;
- compilação Python;
- JSON/YAML;
- workflows via actionlint e Zizmor;
- secret scan;
- dependências;
- frontend;
- segurança e contratos globais.

Workflows Pecuária não substituem esse gate.

### Probes LIVE públicos

O workflow `.github/workflows/pecuaria-production.yml` concentra:
- PPM corrente;
- PPM histórico;
- IBGE Abate;
- SIGSIF;
- amostra representativa de classificação bovina no Comex.

Não manter quatro workflows paralelos para a mesma responsabilidade.

### Homologação GCP

É deliberadamente manual (`workflow_dispatch`) enquanto as fontes estão gated.

Sequência:
1. preflight do bootstrap/datasets;
2. deploy do collector compartilhado e job Pecuária;
3. duas execuções canary de cada uma das quatro fontes;
4. validação de carga e idempotência;
5. gate agregado das tabelas Pecuária;
6. view histórica de carne bovina;
7. deploy do Gateway endurecido;
8. validação E2E das rotas;
9. promoção de fonte somente com evidência completa do contrato de promoção.

Nenhum script recorrente cria IAM ou reduz permissões para fazer o teste passar.

## Pesquisa GitHub e decisões de ferramentas

### Adotar como próxima camada de dados: MapBiomas Pasture

Repositório auditado: `mapbiomas/brazil-pasture`.

Capacidades relevantes:
- pastagens anuais Landsat 30 m;
- produto Sentinel-2 10 m;
- vigor/condição de pastagem por EVI;
- produtividade/biomassa baseada em GPP;
- metodologia pública do MapBiomas/LAPIG.

Uso pretendido no AgroLog:
- área de pastagem municipal;
- rebanho/ha implícito;
- mudança de área;
- vigor e produtividade da pastagem;
- pressão animal;
- degradação/capacidade de suporte como contexto analítico, nunca diagnóstico isolado.

Integração preferida: `mapbiomas/brazil-pasture` + cliente oficial `google/earthengine-api`, com autenticação Google Cloud adequada e exportação controlada para a arquitetura BigQuery/RAW. Não incorporar código Earth Engine antes de definir assets/licença/conta e teste reproduzível.

### Não adotar como fonte: `rpacco/cattlebr_data`

O projeto encontrado usa essencialmente IBGE + PRODES para uma análise derivada. Não acrescenta uma fonte primária nem capacidade que justifique dependência adicional. Conceitos úteis podem ser reproduzidos diretamente a partir das fontes oficiais já governadas.

### Não promover dbt/SQLMesh por antecipação

`dbt-labs/dbt` e `SQLMesh/sqlmesh` seguem como referências fortes para transformação/versionamento SQL, mas o AgroLog já possui loaders, BigQuery, views, contracts e gates próprios. Uma migração geral agora duplicaria responsabilidade.

Critério futuro para adoção:
- reduzir materialmente boilerplate ou custo de manutenção;
- oferecer lineage/versionamento/teste SQL não coberto de forma suficiente;
- benchmark em um fluxo real antes de qualquer migração transversal.

### `agrobr` continua benchmark, não dependência CORE

É uma boa referência de contratos e cobertura de fontes brasileiras, mas sua adoção global adicionaria uma segunda camada de abstração e dependências que duplicam collectors já homologados. O AgroLog reutiliza ideias/endpoints quando úteis e mantém seu próprio controle de RAW, snapshot, vintage e temporalidade.

## Próxima expansão de dados

Ordem recomendada depois da homologação das quatro fontes atuais:

1. MapBiomas Pasture + Earth Engine oficial;
2. preço físico de boi e indicadores autorizados IMEA/CEPEA;
3. B3 futuro de boi quando o contrato/fonte oficial e direitos estiverem definidos;
4. cadastro/atividade de plantas frigoríficas e capacidade quando fonte oficial estiver disponível;
5. movimentação animal/GTA/INDEA-MT quando houver acesso legal e tecnicamente autorizado;
6. USDA cattle/beef e sinais internacionais relevantes, reutilizando o stack USDA já presente no AgroLog;
7. custos de alimentação (milho/farelo), clima, pastagem e logística como drivers externos.

## Camada analítica N6 Pecuária

Somente depois de dados/vintages adequados:

- ciclo pecuário;
- retenção/descarte de fêmeas;
- disponibilidade futura de animais;
- pressão de abate;
- peso médio de carcaça;
- estoque × abate;
- exportação × produção;
- preço/basis;
- pastagem/lotação implícita;
- custos de alimentação;
- risco climático e logístico.

Modelos seguem os mesmos requisitos N6 do AgroLog:
- walk-forward;
- point-in-time;
- baselines simples;
- controle de leakage;
- incerteza/calibração;
- estabilidade temporal;
- promoção somente após evidência fora da amostra.

## Google Cloud, Replit e Claude Code

### Google Cloud

Arquitetura-alvo já está alinhada:
- BigQuery: verdade analítica;
- Cloud Run Jobs: collectors;
- Cloud Run Service: Gateway;
- Artifact Registry: imagens;
- WIF/OIDC: CI/CD sem chave JSON;
- armazenamento RAW externo com hash/proveniência;
- IAM/bootstrap separado de deploy recorrente.

### Claude Code

O repositório já possui `CLAUDE.md`, `.mcp.json`, `AGENTS.md` e workflow multiagente. Claude Code deve consumir o mesmo GitHub e os mesmos contratos; não criar uma cópia divergente do projeto.

### Replit

Replit será ambiente de desenvolvimento, não nova fonte de verdade. A integração só deve começar depois do candidato GitHub estar integralmente verde.

Regras:
- importar/clonar o GitHub canônico;
- nunca iniciar um fork lógico do projeto;
- secrets somente no secret store do ambiente;
- não usar credencial GCP estática versionada;
- ambiente dev deve apontar para recursos de desenvolvimento/homologação, nunca alterar produção por padrão;
- todo código válido volta ao GitHub e passa pelo Full Project Final Gate;
- não promover artefato produzido apenas no Replit sem commit e CI canônicos.

## Critério de conclusão

A Inteligência Pecuária só pode ser chamada de operacional quando, no mesmo release candidato:

- Full Project Final Gate = PASS;
- probes LIVE Pecuária = PASS;
- bootstrap GCP necessário está comprovado;
- quatro fontes canary carregadas e idempotentes;
- RAW/proveniência presentes;
- BigQuery validado;
- Gateway E2E validado;
- source promotion gates completos;
- segurança/lineage/observabilidade/restore aplicáveis em PASS;
- nenhuma fonte é promovida com evidência parcial.

Até lá, o estado correto é `GATED`, nunca “quase produção”.
