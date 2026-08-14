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

O Codex é um componente permanente do projeto e atua prioritariamente como:
- revisor técnico independente do trabalho do Claude Code;
- segunda opinião para arquitetura, schemas, SQL, testes e segurança;
- auditor de diffs, duplicação, regressões e contratos;
- executor de tarefas isoladas quando explicitamente designado.

O Codex não cria uma segunda fonte de verdade. GitHub continua canônico para código/documentação técnica e BigQuery para dados analíticos.

## Governança

- Toda tarefa deve ter Issue classificada exatamente como `Correção`, `Melhoria` ou `Nova função`.
- Fluxo obrigatório: Issue → branch → alteração → testes/revisão → Pull Request → merge manual.
- Não escrever diretamente na `main`.
- Pesquisar Issues, PRs e arquivos equivalentes antes de criar algo novo.
- Achado fora do escopo deve virar nova Issue, não alteração silenciosa.
- A PR deve informar Issues, alterações, validação, riscos, limitações e próximos passos.

## Regras

- Trabalhe sobre o estado atual; não redesenhe do zero sem necessidade.
- Antes de criar arquivo, módulo, schema, SQL ou regra, pesquise responsabilidade equivalente.
- Prefira atualizar/refatorar a fonte canônica existente.
- Não versionar dados RAW, arquivos grandes, credenciais, tokens ou segredos.
- Não executar `DROP`, `TRUNCATE`, `DELETE`, force push ou operação destrutiva sem autorização explícita.
- Preserve `competencia`, `data_referencia`, `data_publicacao`, `data_coleta` e `data_corte_estudo` quando aplicável.
- Diferencie observado, cadastro, cálculo, inferência, estimativa, projeção, sinal indireto e informação negociada/autorizada.
- Para mudanças não triviais: analisar → planejar → revisar → implementar → testar → revisar diff.
- Quando chamado via MCP pelo Claude Code, forneça revisão independente; não concorde automaticamente com a proposta inicial.
- Divergências entre Claude e Codex devem ser resolvidas pelo código, testes, documentação canônica e evidência, não por preferência de modelo.

## Prioridade atual

A prioridade operacional deve ser lida em `docs/BACKLOG.md` e nas Issues abertas. Este arquivo não deve manter uma fila concorrente de prioridades.
