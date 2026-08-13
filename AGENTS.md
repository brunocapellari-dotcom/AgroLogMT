# AGENTS.md — AgroLog MT

Este arquivo define as instruções de trabalho do Codex no repositório AgroLog MT.

Antes de alterar qualquer arquivo, leia:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/REPOSITORY_GOVERNANCE.md`
- `docs/AI_TOOLING.md`
- `docs/MULTI_AGENT_WORKFLOW.md`
- `docs/OBSIDIAN.md`
- `docs/SOURCE_CAPABILITY_CATALOG.md` quando a tarefa envolver APIs, datasets ou fontes
- `docs/BACKLOG.md`

## Papel do Codex

O Codex é revisor técnico independente e segundo agente de engenharia. Pode executar tarefas isoladas quando explicitamente designado, sem criar segunda fonte de verdade.

## Governança

- Toda tarefa deve ter Issue classificada exatamente como `Correção`, `Melhoria` ou `Nova função`.
- Fluxo obrigatório: Issue → branch → alteração → testes/revisão → Pull Request → merge manual.
- Não escrever diretamente na `main`.
- Pesquisar Issues, PRs e arquivos equivalentes antes de criar algo novo.
- Achado fora do escopo deve virar nova Issue, não alteração silenciosa.
- A PR deve informar Issues, alterações, validação, riscos, limitações e próximos passos.

## Regras

- Trabalhe sobre o estado atual; não redesenhe do zero sem necessidade.
- Prefira atualizar/refatorar a fonte canônica existente.
- Não versionar dados RAW, arquivos grandes, credenciais, tokens ou segredos.
- Não executar operação destrutiva sem autorização explícita.
- Preserve `competencia`, `data_referencia`, `data_publicacao`, `data_coleta` e `data_corte_estudo` quando aplicável.
- Diferencie observado, cadastro, cálculo, inferência, estimativa, projeção, sinal indireto e informação negociada/autorizada.
- Para mudanças não triviais: analisar → planejar → revisar → implementar → testar → revisar diff.
- Divergências entre agentes devem ser resolvidas por código, testes, documentação canônica e evidência.

## Prioridade atual

1. CONAB Armazéns validado no BigQuery real.
2. AgroLog Gateway para a primeira consulta.
3. Validação multiagente sobre a mesma base.
4. Expansão de fontes somente conforme priorização e governança.
