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

1. Executar **CONAB Armazéns** ponta a ponta contra o BigQuery real.
2. Validar carga, logs, deduplicação e consulta.
3. Conectar o **AgroLog Gateway** à primeira tabela.
4. Testar a mesma consulta via OpenAI e Claude.
5. Expandir para novas fontes somente após essa validação.

## Estrutura inicial

- `docs/` — arquitetura, governança, backlog e decisões.
- `collector/` — coletores, normalização e cargas.
- `historical/` — componentes históricos e reconstruções.
- `gateway/` — API/MCP AgroLog Gateway.
- `sql/` — consultas, views e transformações SQL.
- `tests/` — testes automatizados e validações.

> A implementação deve evoluir incrementalmente a partir da V3, sem redesenho completo do projeto.
