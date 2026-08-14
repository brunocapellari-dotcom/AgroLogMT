# Governança do Repositório

Este documento é a fonte canônica para organização, criação, alteração e remoção de arquivos no repositório AgroLog MT.

## 1. Responsabilidade principal

- ChatGPT/OpenAI atua como mantenedor principal da estrutura do repositório e responsável por criar, consolidar, revisar e organizar os arquivos do projeto.
- Claude/Claude Code consome o repositório, analisa, testa, revisa e pode propor alterações, mas não deve criar uma segunda fonte de verdade concorrente para a mesma função.
- BigQuery continua sendo a fonte única de verdade analítica dos dados operacionais e históricos. GitHub é a fonte oficial de código, configuração, SQL, documentação e contratos do projeto.

## 2. Regra de não duplicação

Antes de criar qualquer arquivo, diretório, schema, SQL, configuração, documentação ou módulo, o mantenedor deve:

1. inspecionar a estrutura atual do repositório;
2. procurar arquivo ou função equivalente;
3. identificar a fonte canônica já existente;
4. atualizar, estender ou refatorar o conteúdo existente sempre que possível;
5. criar novo arquivo apenas quando houver responsabilidade realmente distinta.

Não criar arquivos com conteúdo substancialmente equivalente apenas para manter versões paralelas, cópias de segurança ou alternativas de implementação dentro da árvore principal.

## 3. Regra de complementaridade

Cada arquivo deve ter uma responsabilidade clara e não sobreposta.

Quando dois conteúdos tratarem do mesmo assunto:

- definir qual deles é a fonte canônica;
- mover para a fonte canônica tudo o que for necessário;
- substituir duplicação por referência curta quando houver relação entre documentos;
- remover ou arquivar de forma controlada o conteúdo redundante depois da validação.

Documentos complementares devem apontar para a fonte canônica em vez de repetir regras extensas.

## 4. Alterações incrementais

O AgroLog MT deve evoluir por melhoria incremental, não por recriação indiscriminada.

Antes de substituir um componente:

- entender o comportamento atual;
- identificar dependências e consumidores;
- preservar interfaces que ainda forem válidas;
- migrar referências de forma coordenada;
- executar testes e validações;
- somente então remover o componente antigo.

Não manter duas implementações ativas para a mesma função sem motivo técnico documentado.

## 5. Fontes canônicas

- `README.md`: visão geral, arquitetura resumida e prioridade atual.
- `docs/ARCHITECTURE.md`: arquitetura técnica canônica.
- `docs/DATA_GOVERNANCE.md`: governança e classificação de dados/evidências.
- `docs/REPOSITORY_GOVERNANCE.md`: governança estrutural do GitHub e colaboração entre agentes.
- `docs/SOURCE_CAPABILITY_CATALOG.md`: contrato do catálogo de fontes e capacidades.
- `docs/OBSIDIAN.md`: arquitetura e escopo do Segundo Cérebro.
- `docs/BACKLOG.md`: prioridades de alto nível; Issues controlam o trabalho rastreável.

Novos documentos devem complementar essas fontes, não reescrevê-las.

## 6. Fluxo obrigatório antes de qualquer mudança

1. Ler a árvore relevante do repositório.
2. Ler os arquivos canônicos relacionados.
3. Pesquisar Issues, PRs, nomes, funções, tabelas, schemas e regras semelhantes.
4. Classificar a mudança e vinculá-la à Issue correspondente.
5. Preferir atualização/refatoração a novo arquivo quando a responsabilidade já existir.
6. Validar que não surgiram duas fontes de verdade.
7. Registrar a mudança de forma clara no commit ou Pull Request.

## 7. Claude e outros agentes

Claude Code e futuros agentes devem tratar o conteúdo atual do repositório como estado oficial do projeto.

Ao propor alterações, devem:

- reutilizar estruturas existentes;
- evitar criar arquivos equivalentes com outro nome;
- evitar redefinir schemas, contratos ou regras já canônicas;
- apontar conflitos antes de implementar;
- preferir alterações pequenas, rastreáveis e testáveis;
- preservar compatibilidade quando tecnicamente apropriado.

## 8. Conflitos de informação

Se houver conflito entre arquivos:

1. não escolher silenciosamente um deles;
2. identificar qual é a fonte canônica pela responsabilidade definida neste documento;
3. consolidar a informação válida na fonte canônica;
4. atualizar referências dependentes;
5. remover a ambiguidade antes de continuar o desenvolvimento.

Nenhum processo automatizado deve depender de duas definições concorrentes para o mesmo conceito.

## 9. Dados brutos e artefatos grandes

O GitHub não deve virar depósito de bases históricas, planilhas de operação ou arquivos grandes que pertencem ao armazenamento de dados.

- BigQuery: dados estruturados e históricos analíticos.
- armazenamento apropriado/Drive quando necessário: documentos-fonte e artefatos pesados.
- GitHub: código, configuração, schemas, SQL, documentação, testes, metadados e pequenos fixtures necessários ao desenvolvimento.

## 10. Governança obrigatória por Issue

Toda tarefa de alteração do repositório deve ter uma classificação exata: **Correção**, **Melhoria** ou **Nova função**.

Fluxo: **Issue → branch → alteração → testes/revisão → Pull Request → merge manual**.

- Não escrever diretamente na `main`.
- Antes de criar branch ou PR, pesquisar trabalho aberto equivalente.
- Uma PR pode referenciar mais de uma Issue quando a mudança for coesa.
- Achado fora do escopo deve virar nova Issue, não alteração silenciosa.
- A PR deve informar Issues, alterações, validação, riscos, limitações e próximos passos.

## 11. Princípio final

Uma função, um contrato, um schema ou uma regra deve possuir uma única fonte canônica no repositório. Todo novo conteúdo deve melhorar, complementar ou referenciar o que já existe — nunca criar uma segunda verdade concorrente.
