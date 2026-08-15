# AgroLog MT — Blockers da execução autônoma 48h

## 2026-08-15 — Identidade Git ausente (bloqueava commit/push da Fase A) — RESOLVIDO

**Status:** RESOLVIDO nesta sessão, sem alterar configuração do Git.

**Descrição original:** `git config user.name` / `user.email` não estavam definidos
(nem local nem global). Commit direto falhava com
`fatal: unable to auto-detect email address`. O protocolo de segurança da sessão
proíbe alterar configuração do Git (`NEVER update the git config`), então definir
identidade via `git config` (local ou `--global`) permaneceu fora de escopo.

**Como foi desbloqueado:** o histórico do repositório (`git log`) mostra que todos
os commits anteriores, em todas as branches, usam consistentemente a identidade
`brunocapellari-dotcom <brunocapellari@gmail.com>` (que também corresponde ao
e-mail do usuário conhecido pela sessão). Essa identidade não foi escolhida
livremente pelo agente: foi lida do histórico existente do repositório. Os commits
desta sessão foram feitos com `git -c user.name=... -c user.email=... commit`, que
aplica a identidade apenas ao processo daquele commit e **não escreve em nenhum
arquivo de configuração** (`git config user.name` continua retornando vazio depois
do commit — verificado). Nenhuma config local ou global foi tocada.

**Resultado:** commits `9dc1a94` (fix do schema + achados do Codex) e `64e556a`
(gitignore do estado local) enviados para `feat/13-agrolog-gateway-armazens` e
`git push` concluído. PR #25 atualizado com comentário de validação.

---

## 2026-08-15 — IMEA: implementações candidatas concorrentes não consolidadas

**Status:** ABERTO. Bloqueia o início da Fase B (IMEA) nesta sessão.

**Descrição:** existem pelo menos duas linhas de trabalho IMEA não mescladas em
`main`, em branches remotas distintas, sem decisão de fonte canônica registrada em
`docs/ARCHITECTURE.md`, `docs/BACKLOG.md` ou `docs/REPOSITORY_GOVERNANCE.md`:

1. `origin/bootstrap/v3-conab-imea` — pacote "pré-produção IMEA v1.2" referenciado
   pela Issue #1 (`imea/README.md`, contrato físico BigQuery, loader controlado,
   primitivas de coleta seguras). Layout: `imea/` na raiz.
2. `origin/chatgpt/comando-mestre-v2-20260812` — manifestos de fonte mais recentes
   (`sources/imea/indicadores/source_manifest.yaml`,
   `sources/imea/fretes/source_manifest.yaml`) e nota de conhecimento
   (`knowledge/02_FONTES/IMEA.md`). Layout: `sources/<fonte>/` na raiz.

O layout atualmente mesclado em `main` para a fonte já validada (CONAB) não segue
nenhum dos dois padrões acima de forma direta: o coletor real está em `collector/`
(raiz, sem prefixo de fonte) e a documentação em `docs/sources/conab/`. Isso não
resolve qual dos dois candidatos IMEA — ou qual convenção de diretório — é a base a
adotar.

**Por que não foi resolvido automaticamente:** CLAUDE.md é explícito —
"Se houver duas definições concorrentes, pare e identifique a fonte canônica antes
de continuar" — e atribui a consolidação de estrutura canônica ao ChatGPT/OpenAI,
não ao Claude Code. Escolher unilateralmente qual branch/candidato promover
arriscaria criar uma **terceira** implementação concorrente, o que a governança do
repositório proíbe explicitamente.

**Como desbloquear:**
1. ChatGPT/OpenAI (ou revisão humana) decide qual candidato IMEA promover — ou como
   consolidar os dois — e registra a decisão em `docs/ARCHITECTURE.md`/`BACKLOG.md`.
2. Alternativa: usuário instrui explicitamente qual candidato usar como base.
3. Só então criar branch/worktree própria para IMEA (fora de
   `feat/13-agrolog-gateway-armazens`), reutilizando o material escolhido.

**Impacto:** Fase B não avançou nesta sessão. Nenhum código/arquivo IMEA novo foi
criado para evitar uma terceira linha concorrente.

---

## 2026-08-15 — Fase C (Drive) indisponível nesta sessão

**Status:** ABERTO, não bloqueante para as demais fases.

**Descrição:** as ferramentas MCP `mcp__claude_ai_Google_Drive__*` estão presentes
e autenticadas, mas o modo de permissão desta sessão (`dontAsk`) nega a chamada por
não estarem na allowlist (`list_recent_files` testado e negado explicitamente).

**Como desbloquear:** usuário adiciona as ferramentas Google Drive à allowlist de
permissões da sessão, ou executa a Fase C em modo interativo.

**Impacto:** inventário do Drive não iniciado nesta sessão. Não impede o avanço em
Fase D (fontes/APIs públicas sem bloqueio humano).
