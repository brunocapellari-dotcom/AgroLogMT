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

**Revalidado em 2026-08-15 (execução 2):** sem mudança — Issue #1 sem novos
comentários, branches candidatas IMEA sem decisão de consolidação, Drive MCP
ainda fora da allowlist.

**Revalidado em 2026-08-15 (execução 3):** sem mudança — `gh issue list`/
`gh pr list`/`gh pr view 25` conferidos, idênticos ao estado registrado.

---

## 2026-08-15 — Coordenação de estrutura: `sources/*/source_manifest.yaml` (não bloqueante)

**Status:** INFORMATIVO — não bloqueia trabalho, mas deve ser checado antes de
iniciar as Issues #16 e #22.

**Descrição:** a branch `origin/chatgpt/comando-mestre-v2-20260812` (não
mesclada em `main`) já define `sources/anp/source_manifest.yaml`,
`sources/comex/source_manifest.yaml` e `sources/portos/source_manifest.yaml`
— cobrindo parte do escopo de Fase D das Issues #16 (energia/diesel/
fertilizantes/macroeconomia) e #22 (comércio global/atividade portuária),
além dos manifestos IMEA já registrados no blocker acima. `main` ainda não
tem nenhum arquivo `sources/`.

**Por que registrar:** por `CLAUDE.md`, ChatGPT/OpenAI mantém a estrutura
canônica; criar uma segunda estrutura de manifesto para ANP/comex/portos sem
checar essa branch (ou seu estado já mesclado, se for o caso) arriscaria uma
definição concorrente. Por isso a Issue #20 (USDA, sem manifesto equivalente
nessa branch) foi priorizada em vez de #16/#22 na execução 2.

**Como desbloquear:** antes de iniciar #16/#22, verificar se
`chatgpt/comando-mestre-v2-20260812` foi mesclada ou se a convenção de
manifesto foi documentada em `docs/ARCHITECTURE.md`/`BACKLOG.md`; seguir essa
convenção em vez de criar uma nova.

**Revalidado em 2026-08-15 (execução 4):** mesma branch checada antes de
iniciar a Issue #17 (dados ferroviários ANTT) — confirmado que não há
manifesto `sources/ferrovias/*` ou `sources/rodovias/*` equivalente lá, então
a Issue #17 foi executada sem risco de duplicação (diferente de #16/#22, que
seguem adiadas). Sem mudança quanto a #16/#22 em si.

---

## 2026-08-15 — ONTL/Infra S.A. inacessível deste ambiente (Issue #17, não bloqueante)

**Status:** ABERTO, não bloqueante — não impediu a conclusão da Issue #17.

**Descrição:** `ontl.infrasa.gov.br` (Observatório Nacional de Transporte e
Logística, fonte complementar citada na Issue #17 para matrizes O/D
multimodais) não pôde ser acessado a partir deste ambiente nesta sessão:
`WebFetch` retornou falha de resolução DNS (`getaddrinfo ETIMEOUT
ontl.infrasa.gov.br`). Não foi possível confirmar de primeira mão o
mecanismo de acesso (download direto, API, GeoPortal/ArcGIS), formato ou
licença — o que a busca web indica sobre o portal não foi verificado e não
deve ser tratado como confirmado.

**Por que não bloqueou a Issue #17:** o dataset SIADE da ANTT (via
`ckan_connector`, portal já validado) já fornece dado observado real de
movimentação ferroviária mensal por rota, incluindo MT — suficiente para
concluir a avaliação/PoC pedida pela Issue #17 sem depender de ONTL.

**Como desbloquear:** repetir o acesso a `ontl.infrasa.gov.br` em uma
execução futura (pode ser bloqueio de rede transitório do ambiente, não
necessariamente do portal); se persistir, considerar acesso via outra
ferramenta/rede antes de descartar a fonte.

**Impacto:** avaliação de ONTL como fonte de matrizes O/D multimodais fica
pendente para uma execução futura. Ver `docs/sources/antt_ferrovias/README.md`.
