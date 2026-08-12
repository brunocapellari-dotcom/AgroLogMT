# Papéis dos agentes de IA

Este documento define responsabilidades complementares. O objetivo é evitar que diferentes agentes façam a mesma coisa ou criem implementações concorrentes.

## Claude

Papel principal: arquitetura, implementação de mudanças amplas e revisão estrutural.

Use Claude quando a tarefa exigir leitura de grande parte do repositório, refatoração transversal, desenho de novos módulos ou revisão de coerência entre código, dados e documentação.

## Codex / OpenAI

Papel principal: segunda implementação/revisão independente, testes, correções e auditoria técnica.

Use Codex para validar a solução de outro agente, implementar tarefas bem delimitadas, produzir testes, revisar regressões e verificar aderência às regras de `AGENTS.md`.

## GitHub Copilot coding agent

Papel principal: execução orientada por Issue dentro do GitHub.

Use o Copilot para tarefas fechadas, com escopo e critérios de aceite claros, preferencialmente iniciadas por Issue. Ele deve trabalhar em branch própria e abrir PR para revisão.

## Grok no Copilot

Grok deve ser tratado como **modelo alternativo dentro do fluxo do Copilot**, não como uma segunda política de engenharia. Ao usar Grok, todas as regras do repositório continuam iguais.

## Regra de independência

Quando a tarefa exigir revisão independente, o revisor deve ser um agente/modelo diferente do autor da alteração sempre que possível.

Exemplo recomendado:
- Claude implementa → Codex revisa.
- Codex implementa → Claude revisa.
- Copilot/Grok implementa → Claude ou Codex revisa.

## Autoridade

Nenhum agente tem autoridade para aprovar seu próprio merge em `main`. Decisões arquiteturais conflitantes devem ser registradas em Issue/PR e submetidas à decisão humana.
