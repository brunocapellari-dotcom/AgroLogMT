# Ferramentas de IA e Extensões

Este documento é o registro canônico de ferramentas externas, agentes, skills e extensões avaliadas para o AgroLog MT.

## Componentes permanentes

**ChatGPT/OpenAI**
- Coordenação, governança, arquitetura e consolidação do GitHub.

**Claude Code**
- Executor principal no notebook para implementação, terminal, testes e GCP/BigQuery.

**Codex**
- Segundo agente de engenharia e revisor técnico independente.
- Integração atual com Claude Code: MCP local usando `codex mcp-server`.
- Arquivos relacionados: `.mcp.json`, `AGENTS.md`, `docs/MULTI_AGENT_WORKFLOW.md` e `docs/CODEX_SETUP_WINDOWS.md`.
- Regra: um agente implementa e o outro revisa; evitar edição concorrente e loops entre agentes.

**Obsidian**
- Segundo Cérebro do AgroLog MT para conhecimento técnico, histórico e contextual.
- Não substitui GitHub nem BigQuery.
- Documento inicial: `docs/OBSIDIAN.md`.

## Radar Tecnológico do AgroLog MT

O projeto passa a manter um Radar Tecnológico como responsabilidade permanente do CONSTRUTOR/coordenação do AgroLog MT.

Objetivo:
- identificar componentes open source que reduzam tempo de desenvolvimento;
- aumentar automação e qualidade de dados;
- melhorar recuperação de conhecimento e capacidade analítica;
- criar capacidades comerciais sem redesenhar o núcleo;
- acompanhar licença, atividade do projeto, segurança, comunidade e risco de dependência.

Regra: componentes do Radar são **peças substituíveis**. BigQuery, GitHub, armazenamento RAW, AgroLog Gateway e Obsidian não são substituídos apenas porque uma ferramenta nova oferece função semelhante.

## Aprovado para adoção controlada

**Superpowers**
- Função: disciplina de planejamento, implementação, teste, depuração e revisão.
- Regra: não substitui `CLAUDE.md`, `AGENTS.md`, governança, testes próprios nem revisão multiagente.
- Status: aprovado para configuração controlada; não vendorizado no repositório.

## Candidatos prioritários do Radar — avaliar antes de produção

A presença nesta seção significa **prioridade de avaliação**, não autorização automática para instalar ou colocar em produção.

### Automação e coleta

**n8n**
- Uso pretendido: gatilhos, automações, webhooks e integrações entre serviços.
- Regra: revisar licença/modelo de uso antes de qualquer oferta comercial ou hospedagem para terceiros.

**Playwright**
- Uso pretendido: navegação determinística em fontes sem API adequada, testes e downloads automatizados.

**browser-use ou agente de navegador equivalente**
- Uso pretendido: tarefas de navegação que exigem interpretação contextual.
- Regra: não substituir coletor determinístico quando houver API/endpoint estável.

**Airbyte**
- Uso pretendido: conectores padronizados para fontes em que o uso do conector seja mais simples e confiável que código próprio.

### Inteligência documental

**Docling**
- Uso pretendido: extração de texto, tabelas, estrutura e metadados de PDFs/documentos.

**Unstructured / Marker**
- Uso pretendido: alternativas/complementos de parsing documental quando demonstrarem desempenho melhor em casos específicos.

### Conhecimento e recuperação

**Qdrant**
- Uso pretendido: camada vetorial/RAG para recuperação semântica.
- Regra: índice vetorial não é fonte de verdade; toda resposta relevante deve ser rastreável à evidência canônica.

**RAGFlow / LlamaIndex / LangChain / AnythingLLM**
- Uso pretendido: avaliar componentes de ingestão, recuperação e orquestração RAG.
- Regra: selecionar somente o mínimo necessário após benchmark; evitar empilhar frameworks equivalentes.

### BI, observabilidade e geointeligência

**Metabase**
- Uso pretendido: BI operacional/analítico para exploração de indicadores.

**Grafana**
- Uso pretendido: observabilidade técnica de pipelines, coletores, filas, jobs e serviços.

**QGIS / GeoServer**
- Uso pretendido: análise espacial e eventual disponibilização controlada de camadas geográficas.

### Orquestração e memória de agentes

**Agno / CrewAI / Semantic Kernel / AutoGen**
- Uso pretendido: candidatos para orquestração formal de agentes.
- Regra: não adotar vários orquestradores simultaneamente; selecionar somente após prova prática.

**mem0 ou mecanismo equivalente**
- Uso pretendido: memória operacional de análises, hipóteses e previsões.
- Regra: GitHub, BigQuery e documentação canônica prevalecem sobre memória de agente.

### Integração WhatsApp para Freight Listener

**Evolution API**
- Uso pretendido: candidato principal inicial para prova técnica de recebimento de mensagens/mídias de canal autorizado e entrega via webhook/fila.

**WPPConnect / WAHA**
- Uso pretendido: alternativas para benchmark de estabilidade, grupos, mídia, operação e manutenção.

Regras específicas:
- integração deve ficar isolada do núcleo do AgroLog;
- nenhuma sessão, cookie, token ou credencial entra no GitHub;
- revisar licença, termos de uso, estabilidade, segurança, privacidade e compatibilidade antes de produção;
- o módulo começa somente como ingestão/observação: não enviar mensagens, contratar fretes ou negociar automaticamente nesta fase.

### Expansão operacional futura

**Traccar / Fleetbase**
- Uso pretendido: telemetria/frota autorizada e inteligência operacional complementar, não criação de TMS genérico.

**ThingsBoard / EMQX / ChirpStack**
- Uso pretendido: IoT, sensores, silos, ativos e telemetria futura.

**Ultralytics / OpenCV / Frigate**
- Uso pretendido: provas controladas de visão computacional para contagem/atividade em pátios, vias e ativos.

## Piloto posterior

**Claude Mem**
- Função: memória entre sessões.
- Regra: GitHub e documentação atual prevalecem sobre memória externa.

**Auditoria / doctor do ambiente Claude**
- Função: identificar skills, hooks, plugins e configurações desnecessárias ou quebradas.
- Status: conceito aprovado; implementação específica deve ser validada antes de instalar.

## Futuro

- Strix: testes de segurança controlados em ambiente autorizado.

## Não incorporar ao núcleo agora

- Agent Reach.
- OmniRoute e roteadores de muitos modelos.
- Listas de APIs/modelos grátis.
- Task Observer/autoevolução de skills.
- Skills de design sem demanda atual.
- Otimizadores de token/contexto não validados.

## Checklist obrigatório antes de adotar ferramenta externa

1. necessidade concreta e ganho mensurável;
2. licença e permissões de uso;
3. atividade/manutenção do projeto;
4. vulnerabilidades e superfície de ataque;
5. tratamento de credenciais e dados sensíveis;
6. dependências e custo operacional;
7. capacidade de substituição/saída;
8. teste com caso real do AgroLog;
9. comparação com capacidade já existente;
10. documentação da decisão.

## Princípio operacional

Ferramenta nova entra apenas se resolver necessidade concreta sem criar segunda fonte de verdade, duplicar capacidade existente ou ampliar desnecessariamente a complexidade do AgroLog MT.
