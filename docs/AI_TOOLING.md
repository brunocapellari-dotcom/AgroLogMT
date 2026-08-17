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

**Claude-Mem — piloto operacional**
- Função: memória operacional entre sessões, inicialmente para Claude Code.
- Objetivo: reduzir reexplicação manual de contexto de implementação, erros, comandos, testes e próximos passos.
- Status: aprovado para piloto controlado pela Issue #35; não é componente canônico de dados, código, arquitetura ou conhecimento.
- Hierarquia obrigatória: BigQuery prevalece para dados; GitHub/documentação prevalecem para código e decisões arquiteturais; Issues/PRs prevalecem para estado do trabalho; Obsidian prevalece para conhecimento consolidado; Claude-Mem é apenas memória operacional auxiliar.
- Memória externa nunca prevalece sobre o conteúdo atual do GitHub.
- Não persistir credenciais, tokens, chaves, segredos, dados pessoais desnecessários ou conteúdo bruto sensível.
- A configuração deve permitir desligamento/rollback sem impedir o funcionamento do projeto.
- O piloto deve medir continuidade entre sessões, relevância do contexto recuperado, falsos contextos, custo de manutenção e risco de informação desatualizada.
- A adoção permanente depende de evidência prática do piloto e documentação de instalação, segurança, retenção e rollback.

## Piloto posterior

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
- Caveman até existir benchmark interno que demonstre ganho líquido de custo/contexto sem perda de governança ou qualidade.

## Princípio operacional

Ferramenta nova entra apenas se resolver necessidade concreta sem criar segunda fonte de verdade, duplicar capacidade existente ou ampliar desnecessariamente a complexidade do AgroLog MT.
