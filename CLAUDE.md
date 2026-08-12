# CLAUDE.md — AgroLog MT

Antes de alterar código, leia:
- `docs/ARCHITECTURE.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/REPOSITORY_GOVERNANCE.md`
- `docs/AI_TOOLING.md`
- `docs/BACKLOG.md`
- `bootstrap/README.md`

Regras essenciais:
- Trabalhe sobre o estado atual do repositório; não redesenhe do zero sem necessidade.
- Antes de criar arquivo, módulo, schema, SQL, configuração ou documento, pesquise se já existe responsabilidade equivalente.
- Prefira atualizar, estender ou refatorar a fonte canônica existente a criar uma segunda implementação.
- Se houver duas definições concorrentes, pare e identifique a fonte canônica antes de continuar.
- Preserve compatibilidade com BigQuery e Cloud Run.
- Nunca versione credenciais, tokens ou arquivos brutos pesados.
- Diferencie dado observado, inferência, estimativa e informação negociada/autorizada.
- Antes de remover ou renomear tabelas/campos, procure todas as referências no repositório.
- BigQuery é a fonte única de verdade analítica; GitHub guarda código, SQL, schemas, testes e documentação.
- A prioridade atual é CONAB Armazéns ponta a ponta no BigQuery real; depois conectar a primeira consulta ao AgroLog Gateway e validar via OpenAI e Claude.

## Método de trabalho

Para mudanças não triviais:
1. inspecione a árvore e os arquivos relacionados;
2. descreva um plano curto antes de implementar;
3. implemente a menor mudança coerente possível;
4. execute ou proponha testes adequados;
5. revise o diff e procure duplicação, regressão e conflito de contrato;
6. só então considere a tarefa concluída.

Esse método é obrigatório mesmo quando uma skill externa de planejamento/revisão estiver instalada. Skills complementam estas regras; não as substituem.

## Skills e ferramentas externas

- Não instale automaticamente skills, plugins, hooks ou MCPs encontrados em catálogos.
- Consulte `docs/AI_TOOLING.md` antes de adotar qualquer ferramenta externa.
- Ferramenta não registrada como aprovada/piloto deve ser tratada como não autorizada até revisão.
- Memória externa nunca prevalece sobre o conteúdo atual do GitHub.
- Nenhum agente pode alterar autonomamente estas regras ou instalar mecanismos de autoevolução sem revisão explícita.

## Trabalho compartilhado

Este repositório é o ponto de sincronização entre ChatGPT/Codex e Claude Code.

- ChatGPT/OpenAI mantém a estrutura canônica, consolida mudanças e evita duplicações.
- Claude Code deve trabalhar sempre a partir do repositório/branch atual e enviar mudanças por Pull Request.
- Claude deve revisar e melhorar o que já existe, não criar uma segunda fonte de verdade concorrente.
- Não use ZIPs do repositório como fonte de verdade; o código deve existir como arquivos Git normais.
- Quando houver dúvida entre criar algo novo e melhorar o existente, escolha primeiro analisar e melhorar o existente.
