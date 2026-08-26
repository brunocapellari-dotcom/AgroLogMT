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
- **Provedores externos de inteligência**: serviços independentes podem fornecer sinais ao AgroLog por API/feed versionado; não compartilham banco, credenciais ou código interno com o AgroLog.

### Programa Integrado Radar

As melhorias derivadas do Radar GitHub são incorporadas como três frentes complementares da mesma arquitetura:

1. **Coleta, documentos e qualidade** — automação, navegação controlada, inteligência documental, detecção de atualização, diff, auditoria e linhagem.
2. **Inteligência, conhecimento e observabilidade** — RAG, memória, agentes, avaliação previsto × realizado, BI, observabilidade e geointeligência.
3. **Expansão operacional e comercial** — Freight Listener, sinais de mercado, telemetria/IoT/visão futuros e produtos controlados pelo AgroLog Gateway.

Os componentes open source avaliados são peças substituíveis. Eles não substituem as fontes canônicas do projeto apenas por oferecerem função semelhante. A seleção tecnológica e os gates de adoção estão em `docs/TECHNOLOGY_STACK.md`.

### Freight Listener

O Freight Listener é o módulo para transformar mensagens e mídias de **canais autorizados** em observações estruturadas de ofertas de frete. A oferta anunciada é tratada como `observado` com subtipo `oferta_frete_observada`; isso não comprova contratação, execução nem frete efetivamente pago. O módulo inclui normalização, deduplicação, reoferta, reajuste, persistência e sinais agregados, com PII minimizada e evidência original preservada fora do GitHub.

### Inteligência geopolítica externa

O **Geopolitical Watch** é um projeto independente. Ele pode fornecer eventos, clusters, notícias e reports ao AgroLog MT por uma interface publicada e versionada. O AgroLog atua apenas como consumidor: preserva a evidência recebida e faz sua própria análise de relevância para agricultura, energia, fertilizantes, comércio, câmbio e logística.

## Documentação principal

- `docs/ARCHITECTURE.md` — arquitetura oficial.
- `docs/TECHNOLOGY_STACK.md` — seleção tecnológica, estados de adoção e gates de promoção.
- `docs/DATA_GOVERNANCE.md` — governança dos dados.
- `docs/REPOSITORY_GOVERNANCE.md` — governança do GitHub.
- `docs/AI_TOOLING.md` — agentes, ferramentas, Radar Tecnológico e extensões avaliadas.
- `docs/MULTI_AGENT_WORKFLOW.md` — fluxo Claude Code + Codex + ChatGPT.
- `docs/CODEX_SETUP_WINDOWS.md` — instalação e teste do Codex no notebook.
- `docs/OBSIDIAN.md` — papel do Segundo Cérebro.
- `docs/N6_PROGRAM.md` — programa científico N6 e gates de promoção.
- `docs/N6_EXECUTION_STATUS.md` — estado operacional e evidências do ciclo N6.
- `docs/SOY_MT_DATAMART.md` — contrato do primeiro Data Mart vertical.
- `docs/FREIGHT_LISTENER.md` — especificação canônica da inteligência de ofertas observadas.
- `docs/EXTERNAL_GEOPOLITICAL_INTELLIGENCE.md` — contrato de consumo do Geopolitical Watch como provedor externo.
- `docs/BACKLOG.md` — prioridades de implantação e três frentes integradas.

## Governança do repositório

O GitHub é a fonte oficial para código, configurações, SQL, schemas, documentação e contratos do projeto. Antes de criar ou alterar arquivos, deve-se analisar o que já existe e preferir consolidar, atualizar e refatorar estruturas existentes em vez de gerar duplicatas ou fontes concorrentes.

## Separação entre código e dados

Nomes de fontes como **CONAB**, **IMEA**, **CEPEA**, **Comex Stat**, **ANTAQ**, **ANP** ou **USDA** podem aparecer na árvore do repositório para identificar qual origem um coletor, parser, schema, configuração ou teste atende. Isso não significa que os arquivos reais dessas fontes devam ser armazenados no GitHub.

A separação oficial é:

- **GitHub** — código, coletores, parsers, schemas, SQL, configurações sem segredo, testes e documentação;
- **armazenamento externo/RAW** — arquivos originais e históricos das fontes, planilhas, ZIPs, PDFs, mensagens/mídias autorizadas e demais dados operacionais;
- **BigQuery** — dados estruturados, históricos tratados e camada analítica oficial;
- **Obsidian** — conhecimento derivado, relações, explicações e memória histórica.

Dados reais não devem ser copiados para o repositório apenas para permitir testes. Os testes que exigirem bases reais devem receber caminho externo/configurável para esses dados. Fixtures pequenos e artificiais podem permanecer em `tests/fixtures/` quando necessários.

## Organização por responsabilidade

A árvore deve evoluir incrementalmente conforme os módulos reais forem incorporados. Não criar diretórios vazios apenas para antecipar fontes futuras.

- `docs/` — arquitetura, governança, agentes, conhecimento, backlog e decisões;
- `collector/` — motor de coleta/normalização e componentes específicos de fonte;
- `historical/` — reconstruções e cargas históricas;
- `gateway/` — API/MCP AgroLog Gateway;
- `models/` — registros, primitives quantitativas e modelos;
- `contracts/` — contratos canônicos de dados/fontes;
- `sql/` — consultas, views e transformações SQL;
- `tests/` — testes automatizados, validações e fixtures pequenos/artificiais;
- `scripts/` — deploy, homologação, QA e utilitários operacionais;
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

- `observado`;
- `estimado`;
- `projetado`;
- `inferido`;
- `sinal_qualitativo`;
- `negociado_autorizado`.

`data_referencia` não é data de disponibilidade. Estudos históricos e backtests devem usar apenas vintages efetivamente disponíveis no momento de corte.

## Prioridade atual

1. Homologar **CONAB Armazéns** e o **AgroLog Gateway** no GCP real com `scripts/homologate_n6_core.sh`.
2. Manter **CONAB Safra** tecnicamente pronta, com parser/live probe point-in-time, mas desabilitada em produção até o gate P0/P1.
3. Migrar incrementalmente o trabalho comprovado do **IMEA Agro v1.2** para a arquitetura N6 atual.
4. Implementar **Comex Stat** com ingestão streaming/chunked e sem confundir URF com porto.
5. Integrar **clima/hidrologia** preservando a natureza da evidência (estação, produto modelado, reanálise, forecast).
6. Materializar o **Data Mart Soja MT** somente após QA das tabelas canônicas de origem.
7. Treinar, validar e auditar os primeiros modelos N6 apenas com datasets point-in-time homologados.

> A implementação deve evoluir incrementalmente a partir do estado atual do projeto, sem redesenho completo e sem criar uma segunda fonte de verdade.
