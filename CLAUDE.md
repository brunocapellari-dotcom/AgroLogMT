# CLAUDE.md — AgroLog MT

Antes de alterar código, leia:
- `docs/ARCHITECTURE.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/REPOSITORY_GOVERNANCE.md`
- `docs/AI_TOOLING.md`
- `docs/MULTI_AGENT_WORKFLOW.md`
- `docs/BACKLOG.md`
- `bootstrap/README.md`

Regras essenciais:
- Trabalhe sobre o estado atual do repositório; não redesenhe do zero sem necessidade.
- Antes de criar arquivo, módulo, schema, SQL, configuração ou documento, pesquise se já existe responsabilidade equivalente.
- Prefira atualizar, estender ou refatorar a fonte canônica existente a criar uma segunda implementação.
- Se houver duas definições concorrentes, pare e identifique a fonte canônica antes de continuar.
- Preserve compatibilidade com BigQuery e Cloud Run.
- Nunca versione credenciais, tokens ou arquivos brutos pesados.
- Nomes de fontes como CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANP e USDA identificam responsabilidades de código; não autorizam armazenar datasets reais no GitHub.
- Código, parsers, schemas, SQL, configurações sem segredo, testes e documentação pertencem ao GitHub; dados reais/RAW e históricos pesados ficam em armazenamento externo.
- Testes que dependam de dados reais devem receber caminho externo/configurável.
- Fixtures pequenos e artificiais podem permanecer em `tests/fixtures/` quando necessários.
- Diferencie dado observado, inferência, estimativa e informação negociada/autorizada.
- Antes de remover ou renomear tabelas/campos, procure todas as referências no repositório.
- BigQuery é a fonte única de verdade analítica; GitHub guarda código, SQL, schemas, testes e documentação; Obsidian guarda conhecimento derivado.
- A prioridade atual é CONAB Armazéns ponta a ponta no BigQuery real, depois AgroLog Gateway e expansão de fontes.

## Método de trabalho

Para mudanças não triviais:
1. inspecione a árvore e os arquivos relacionados;
2. descreva um plano curto;
3. quando o MCP `codex` estiver disponível, peça ao Codex uma revisão independente do plano para mudanças materiais;
4. implemente a menor mudança coerente possível;
5. execute testes adequados;
6. revise o diff;
7. quando aplicável, peça ao Codex revisão final do diff;
8. só então considere a tarefa concluída.

Codex é revisor/segundo agente, não fonte de verdade. Divergências devem ser resolvidas com código, testes, documentação canônica e evidência.

## Organização por fonte

- Não crie diretórios vazios apenas para antecipar fontes futuras.
- Identifique claramente a fonte atendida pelo código sem misturar arquivos RAW.
- Preserve componentes compartilhados quando a regra for comum a várias fontes.
- Adapte estruturas existentes incrementalmente em vez de mover arquivos apenas para seguir desenho teórico.

## Skills e ferramentas externas

- Consulte `docs/AI_TOOLING.md` antes de adotar ferramenta externa.
- Codex e Obsidian são componentes permanentes já aprovados.
- Claude-Mem está aprovado apenas para piloto operacional controlado conforme `docs/AI_TOOLING.md` e Issue #35.
- Ao usar Claude-Mem, trate a memória recuperada como contexto auxiliar: releia GitHub, documentação, Issue e PR atuais antes de agir quando houver risco de conflito ou desatualização.
- Não permita que Claude-Mem persista credenciais, tokens, chaves, segredos ou dados sensíveis desnecessários.
- Não instale automaticamente skills, plugins ou hooks não aprovados.
- Memória externa nunca prevalece sobre o conteúdo atual do GitHub.
- Nenhum agente pode alterar autonomamente estas regras ou instalar mecanismos de autoevolução sem revisão explícita.

## Trabalho compartilhado

Este repositório é o ponto de sincronização entre ChatGPT/OpenAI, Claude Code e Codex.

- ChatGPT/OpenAI mantém estrutura canônica, consolida mudanças e evita duplicações.
- Claude Code é o executor principal no ambiente local.
- Codex atua como revisão independente e segundo agente, preferencialmente via MCP conforme `docs/MULTI_AGENT_WORKFLOW.md`.
- Obsidian é a camada de conhecimento e não deve competir com GitHub ou BigQuery.
- Não use ZIPs como fonte de verdade de código; o código deve existir como arquivos Git normais.
- Quando houver dúvida entre criar algo novo e melhorar o existente, analise e melhore o existente primeiro.
