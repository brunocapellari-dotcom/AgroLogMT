# AgroLog MT

Repositório central do projeto **AgroLog MT**.

## Objetivo

Construir uma plataforma de inteligência em agronegócio e logística com foco inicial em Mato Grosso e no eixo BR-163, evoluindo de análise informativa para inteligência preditiva e apoio à decisão.

## Arquitetura oficial

- **BigQuery**: fonte única de verdade analítica.
- **Cloud Run**: camada de serviços e acesso.
- **AgroLog Gateway**: API/MCP própria para expor consultas e ações controladas.
- **ChatGPT/OpenAI**: coordenação, governança, arquitetura e consolidação do GitHub.
- **Claude Code**: executor principal no ambiente local para implementação, testes e GCP/BigQuery.
- **Codex**: segundo agente de engenharia e revisor técnico independente, integrado ao Claude Code por MCP.
- **Obsidian**: Segundo Cérebro permanente do projeto para conhecimento técnico, histórico e contextual.
- **PostgreSQL**: reservado para eventual camada transacional futura.

## Documentação principal

- `docs/ARCHITECTURE.md` — arquitetura oficial.
- `docs/DATA_GOVERNANCE.md` — governança dos dados.
- `docs/REPOSITORY_GOVERNANCE.md` — governança do GitHub.
- `docs/AI_TOOLING.md` — agentes, ferramentas e extensões aprovadas.
- `docs/MULTI_AGENT_WORKFLOW.md` — fluxo Claude Code + Codex + ChatGPT.
- `docs/CODEX_SETUP_WINDOWS.md` — instalação e teste do Codex no notebook.
- `docs/OBSIDIAN.md` — papel do Segundo Cérebro.
- `docs/BACKLOG.md` — prioridades de implantação.

## Governança do repositório

O GitHub é a fonte oficial para código, configurações, SQL, schemas, documentação e contratos do projeto. Antes de criar ou alterar arquivos, deve-se analisar o que já existe e preferir consolidar, atualizar e refatorar estruturas existentes em vez de gerar duplicatas ou fontes concorrentes.

## Separação entre código e dados

Nomes de fontes como **CONAB**, **IMEA**, **CEPEA**, **Comex Stat**, **ANTAQ**, **ANP** ou **USDA** podem aparecer na árvore do repositório para identificar qual origem um coletor, parser, schema, configuração ou teste atende. Isso não significa que os arquivos reais dessas fontes devam ser armazenados no GitHub.

A separação oficial é:

- **GitHub** — código, coletores, parsers, schemas, SQL, configurações sem segredo, testes e documentação;
- **armazenamento externo/RAW** — arquivos originais e históricos das fontes, planilhas, ZIPs, PDFs e demais dados operacionais;
- **BigQuery** — dados estruturados, históricos tratados e camada analítica oficial;
- **Obsidian** — conhecimento derivado, relações, explicações e memória histórica.

Dados reais não devem ser copiados para o repositório apenas para permitir testes. Os testes que exigirem bases reais devem receber caminho externo/configurável para esses dados. Fixtures pequenos e artificiais podem permanecer em `tests/fixtures/` quando necessários.

## Organização por responsabilidade

A árvore deve evoluir incrementalmente conforme os módulos reais forem incorporados. Não criar diretórios vazios apenas para antecipar fontes futuras.

- `docs/` — arquitetura, governança, agentes, conhecimento, backlog e decisões;
- `collector/` — motor de coleta/normalização e componentes específicos de fonte;
- `historical/` — reconstruções e cargas históricas;
- `gateway/` — API/MCP AgroLog Gateway;
- `sql/` — consultas, views e transformações SQL;
- `tests/` — testes automatizados, validações e fixtures pequenos/artificiais;
- `bootstrap/` — instruções de sincronização e implantação inicial;
- `AGENTS.md` — instruções de trabalho do Codex;
- `.mcp.json` — configuração de MCP compartilhada do projeto.

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
3. Validar carga, logs, deduplicação e idempotência.
4. Conectar o **AgroLog Gateway** à primeira tabela.
5. Validar o fluxo de engenharia Claude Code + Codex.
6. Testar a mesma base via OpenAI e Claude.
7. Expandir para novas fontes somente após essa validação, começando pelo IMEA.

> A implementação deve evoluir incrementalmente a partir do estado atual do projeto, sem redesenho completo e sem criar uma segunda fonte de verdade.
