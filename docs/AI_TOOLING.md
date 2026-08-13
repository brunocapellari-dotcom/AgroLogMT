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

## Aprovado para adoção controlada

**Superpowers**
- Função: disciplina de planejamento, implementação, teste, depuração e revisão.
- Regra: não substitui `CLAUDE.md`, `AGENTS.md`, governança, testes próprios nem revisão multiagente.
- Status: aprovado para configuração controlada; não vendorizado no repositório.

## Piloto posterior

**Claude Mem**
- Função: memória entre sessões.
- Regra: GitHub e documentação atual prevalecem sobre memória externa.

**Auditoria / doctor do ambiente Claude**
- Função: identificar skills, hooks, plugins e configurações desnecessárias ou quebradas.
- Status: conceito aprovado; implementação específica deve ser validada antes de instalar.

## Futuro

- Strix: testes de segurança controlados em ambiente autorizado.
- Evolution API: integração futura de WhatsApp.

## Não incorporar ao núcleo agora

- Agent Reach.
- OmniRoute e roteadores de muitos modelos.
- Listas de APIs/modelos grátis.
- Task Observer/autoevolução de skills.
- Skills de design sem demanda atual.
- Otimizadores de token/contexto não validados.

## Princípio operacional

Ferramenta nova entra apenas se resolver necessidade concreta sem criar segunda fonte de verdade, duplicar capacidade existente ou ampliar desnecessariamente a complexidade do AgroLog MT.
