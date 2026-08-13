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
- `docs/sources/conab/` — estado, validações e próximos passos da integração CONAB.

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

- `docs/` — arquitetura, governança, agentes, conhecimento, backlog e decisões;
- `collector/` — motor de coleta/normalização e componentes específicos de fonte;
- `historical/` — reconstruções e cargas históricas;
- `gateway/` — API/MCP AgroLog Gateway;
- `sql/` — consultas, views, validações e transformações SQL;
- `tests/` — testes automatizados e validações quando houver componentes compartilhados;
- `bootstrap/` — instruções de sincronização e implantação inicial;
- `AGENTS.md` — instruções de trabalho do Codex;
- `.mcp.json` — configuração de MCP compartilhada do projeto.

## Marco atual — CONAB Armazéns

Em **13/08/2026**, o grupo **CONAB Armazéns** foi validado no BigQuery real:

- 18.807 armazéns;
- 1 snapshot `COMPLETO`;
- 18.807 membros de snapshot;
- MT: 2.917 armazéns, 107 municípios e 58.368.190 t;
- repetição do mesmo pacote sem duplicação analítica;
- contadores de movimento idempotentes após correção mínima descoberta no teste real.

Evidência: `docs/sources/conab/VALIDATION_2026-08-13.md`.

## Princípios de dados

Toda informação deve preservar, quando aplicável:

- `data_referencia`
- `data_publicacao`
- `data_coleta`
- `competencia`

E deve ser classificada explicitamente como dado observado, inferência, estimativa ou informação negociada/autorizada.

## Prioridade atual

1. Consolidar o código CONAB validado no repositório oficial. **Concluído por esta integração.**
2. Conectar a primeira tabela validada ao **AgroLog Gateway**.
3. Validar a mesma consulta via OpenAI/Codex e Claude.
4. Testar a coleta HTTP oficial ao vivo de Armazéns e o workflow de QUARENTENA.
5. Estruturar RAW definitivo em Cloud Storage e, depois, Cloud Run/Scheduler.
6. Expandir as demais famílias CONAB gradualmente.
7. Avançar a integração IMEA em paralelo conforme a base e os contratos estiverem prontos.

> A implementação deve evoluir incrementalmente a partir do estado atual do projeto, sem redesenho completo e sem criar uma segunda fonte de verdade.
