# AGENTS.md — AgroLog MT

Este arquivo define as instruções de trabalho do Codex no repositório AgroLog MT.

Antes de alterar qualquer arquivo, leia:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/REPOSITORY_GOVERNANCE.md`
- `docs/AI_TOOLING.md`
- `docs/MULTI_AGENT_WORKFLOW.md`
- `docs/OBSIDIAN_SECOND_BRAIN.md`
- `docs/BACKLOG.md`

## Papel do Codex

O Codex é um componente permanente do projeto e atua prioritariamente como:
- revisor técnico independente do trabalho do Claude Code;
- segunda opinião para arquitetura, schemas, SQL, testes e segurança;
- auditor de diffs, duplicação, regressões e contratos;
- executor de tarefas isoladas quando explicitamente designado.

O Codex não cria uma segunda fonte de verdade. GitHub continua canônico para código/documentação e BigQuery para dados analíticos.

## Regras

- Trabalhe sobre o estado atual; não redesenhe do zero sem necessidade.
- Antes de criar arquivo, módulo, schema, SQL ou regra, pesquise responsabilidade equivalente.
- Prefira atualizar/refatorar a fonte canônica existente.
- Não versionar dados RAW, arquivos grandes, credenciais, tokens ou segredos.
- Não executar `DROP`, `TRUNCATE`, `DELETE`, force push ou operação destrutiva sem autorização explícita.
- Preserve `data_referencia`, `data_publicacao`, `data_coleta` e `competencia` quando aplicável.
- Diferencie dado observado, inferência, estimativa e informação negociada/autorizada.
- Para mudanças não triviais: analisar → planejar → revisar → implementar → testar → revisar diff.
- Quando chamado via MCP pelo Claude Code, forneça revisão independente; não concorde automaticamente com a proposta inicial.
- Divergências entre Claude e Codex devem ser resolvidas pelo código, testes, documentação canônica e evidência, não por preferência de modelo.

## Prioridade atual

1. CONAB Armazéns ponta a ponta no BigQuery real.
2. Validar carga, logs, deduplicação e idempotência.
3. Integrar primeira consulta ao AgroLog Gateway.
4. Validar a mesma base via OpenAI/Codex e Claude.
5. Expandir fontes somente depois da validação do piloto.
