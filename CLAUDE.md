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
- Nomes de fontes como CONAB, IMEA, CEPEA, Comex Stat, ANTAQ, ANP e USDA identificam responsabilidades de código; não autorizam armazenar os datasets reais dessas fontes no GitHub.
- Código, parsers, schemas, SQL, configurações sem segredo, testes e documentação pertencem ao GitHub; dados reais/RAW, planilhas, ZIPs, PDFs e históricos pesados ficam em armazenamento externo.
- Testes que dependam de dados reais devem receber caminho externo/configurável. Não copie dados reais para dentro do repositório só para fazer o teste passar.
- Fixtures pequenos e artificiais podem permanecer em `tests/fixtures/` quando necessários.
- Diferencie dado observado, inferência, estimativa e informação negociada/autorizada.
- Antes de remover ou renomear tabelas/campos, procure todas as referências no repositório.
- BigQuery é a fonte única de verdade analítica; GitHub guarda código, SQL, schemas, testes e documentação.
- A prioridade atual é consolidar no Git o código validado de CONAB Armazéns, mantendo os dados reais fora do repositório; depois executar a carga ponta a ponta no BigQuery real, conectar a primeira consulta ao AgroLog Gateway e validar via OpenAI e Claude.

## Método de trabalho

Para mudanças não triviais:
1. inspecione a árvore e os arquivos relacionados;
2. descreva um plano curto antes de implementar;
3. implemente a menor mudança coerente possível;
4. execute ou proponha testes adequados;
5. revise o diff e procure duplicação, regressão e conflito de contrato;
6. só então considere a tarefa concluída.

Esse método é obrigatório mesmo quando uma skill externa de planejamento/revisão estiver instalada. Skills complementam estas regras; não as substituem.

## Organização por fonte

- Não crie diretórios vazios apenas para antecipar fontes futuras.
- Quando uma fonte entrar em produção, identifique-a claramente na estrutura do código sem misturar arquivos RAW.
- Preserve componentes compartilhados quando a regra for comum a várias fontes; não replique a mesma lógica em `conab`, `imea` ou outros módulos apenas por organização visual.
- Se a implementação existente já possuir uma estrutura funcional, adapte-a incrementalmente em vez de mover arquivos apenas para seguir um desenho teórico.

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
