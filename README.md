# AgroLog MT

Repositório central do projeto **AgroLog MT**.

## Objetivo

Construir uma plataforma de inteligência em agronegócio e logística com foco inicial em Mato Grosso e no eixo BR-163, evoluindo de análise informativa para inteligência preditiva e apoio à decisão.

## Arquitetura oficial

- **BigQuery**: fonte única de verdade analítica.
- **Cloud Run**: camada de serviços e acesso.
- **AgroLog Gateway**: API/MCP própria para expor consultas e ações controladas.
- **OpenAI/ChatGPT e Claude**: consumidores da mesma base central, sem bancos separados por IA.
- **PostgreSQL**: reservado para eventual camada transacional futura.

## Governança do repositório

O GitHub é a fonte oficial para código, configurações, SQL, schemas, documentação e contratos do projeto. O mantenedor principal deve sempre analisar o que já existe antes de criar ou alterar arquivos, preferindo consolidar, atualizar e refatorar estruturas existentes em vez de gerar duplicatas ou fontes concorrentes.

A regra canônica completa está em `docs/REPOSITORY_GOVERNANCE.md`.

## Separação entre código e dados

Nomes de fontes como **CONAB**, **IMEA**, **CEPEA**, **Comex Stat**, **ANTAQ**, **ANP** ou **USDA** podem aparecer na árvore do repositório para identificar qual origem um coletor, parser, schema, configuração ou teste atende. Isso não significa que os arquivos reais dessas fontes devam ser armazenados no GitHub.

A separação oficial é:

- **GitHub** — código, coletores, parsers, schemas, SQL, configurações sem segredo, testes e documentação;
- **armazenamento externo/RAW** — arquivos originais e históricos das fontes, planilhas, ZIPs, PDFs e demais dados operacionais;
- **BigQuery** — dados estruturados, históricos tratados e camada analítica oficial.

Dados reais não devem ser copiados para o repositório apenas para permitir testes. Os testes que exigirem bases reais devem receber um caminho externo/configurável para esses dados. Fixtures pequenos e artificiais podem permanecer em `tests/fixtures/` quando necessários.

## Organização por responsabilidade

A árvore deve evoluir incrementalmente conforme os módulos reais forem incorporados. Não criar diretórios vazios apenas para antecipar fontes futuras.

- `docs/` — arquitetura, governança, backlog e decisões;
- `collector/` — motor de coleta/normalização e componentes específicos de fonte quando entrarem em produção;
- `historical/` — reconstruções e cargas históricas;
- `gateway/` — API/MCP AgroLog Gateway;
- `sql/` — consultas, views e transformações SQL;
- `tests/` — testes automatizados, validações e fixtures pequenos/artificiais;
- `bootstrap/` — instruções de sincronização e implantação inicial.

Quando uma fonte possuir implementação própria, o nome da fonte deve identificar claramente a responsabilidade do código, sem misturar dados brutos. A estrutura exata deve respeitar o código existente e evitar reorganizações artificiais que criem duplicação.

## Princípios de dados

Toda informação deve preservar, quando aplicável:

- `data_referencia`
- `data_publicacao`
- `data_coleta`
- `competencia`

E deve ser classificada explicitamente como:

- dado observado;
- inferência;
- estimativa;
- informação negociada/autorizada.

## Prioridade atual

1. Consolidar no repositório oficial o código já validado de **CONAB Armazéns**, mantendo os dados reais fora do GitHub.
2. Executar CONAB Armazéns ponta a ponta contra o BigQuery real.
3. Validar carga, logs, deduplicação e consulta.
4. Conectar o **AgroLog Gateway** à primeira tabela.
5. Testar a mesma consulta via OpenAI e Claude.
6. Expandir para novas fontes somente após essa validação, começando pelo IMEA.

> A implementação deve evoluir incrementalmente a partir do estado atual do projeto, sem redesenho completo e sem criar uma segunda fonte de verdade.
