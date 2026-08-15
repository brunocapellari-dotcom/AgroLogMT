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

**Revalidado em 2026-08-15 (execução 7):** chamada real repetida
(`mcp__claude_ai_Google_Drive__list_recent_files`, schema carregado via
`ToolSearch` sem problema). A chamada em si foi negada explicitamente com
`Permission to use mcp__claude_ai_Google_Drive__list_recent_files has been
denied because Claude Code is running in don't ask mode` — confirma que o
bloqueio é de permissão/allowlist da sessão (`dontAsk`), não de
autenticação OAuth (a ferramenta nem aparece na lista de servidores MCP
que exigem autorização desta sessão). A nota da execução 6, que
levantava a hipótese de o blocker ter mudado só porque a ferramenta
aparecia autenticada, fica resolvida: **não mudou** — segue exigindo que
o usuário adicione as ferramentas Drive à allowlist ou rode em modo
interativo.

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

---

## 2026-08-15 — Issue #14: USDA FAS Open Data, NASS Quick Stats e AMS MyMarketNews exigem chave nova

**Status:** ABERTO, não bloqueante — bloqueia só três das quatro fontes da
Issue #14; a quarta (CFTC Commitments of Traders) foi implementada nesta
sessão sem depender deste blocker.

**Descrição:** as quatro fontes aprovadas pela Issue #14 foram testadas
diretamente (chamada HTTP real, sem chave) antes de decidir o que
implementar:

- USDA AMS MyMarketNews (`marsapi.ams.usda.gov/services/v1.2/reports`):
  `HTTP 403 Forbidden` — `"Attempt to access the protected resource"`.
- USDA FAS Open Data / PSD (`apps.fas.usda.gov/OpenData/api/psd/commodities`):
  timeout de conexão — não foi possível nem confirmar o tipo de erro por
  bloqueio de rede neste ambiente; a documentação oficial da API exige
  `X-Api-Key`.
- USDA NASS Quick Stats (`quickstats.nass.usda.gov/api/api_GET/`): `HTTP
  401 Unauthorized` mesmo com `key=DEMO_KEY` — exige registro de chave
  real, chave de demonstração não é aceita.

As três exigem "chave nova" no sentido da regra de Fase D ("fontes que não
exijam compra/chave nova"), então ficam fora do escopo de "sem bloqueio
humano" desta rodada. Evidência completa em
`docs/sources/cftc_cot/README.md` (seção "Fontes da Issue #14 fora do
escopo desta avaliação").

**Como desbloquear:** usuário decide se registra as chaves de API
necessárias (USDA FAS Open Data e NASS Quick Stats têm registro gratuito
por e-mail; AMS MyMarketNews também exige registro) e onde armazená-las
com segurança (nunca em texto plano no Git, conforme `CLAUDE.md`). Só
então retomar a avaliação dessas três fontes dentro da Issue #14.

**Impacto:** Issue #14 permanece parcialmente atendida — subconjunto CFTC
COT implementado e enviado (PR #32); as outras três fontes aguardam
decisão humana sobre credenciais.

---

## 2026-08-15 — Issue #14/#20: duplicação remanescente de cliente Socrata em `usda_agtransport` (não bloqueante)

**Status:** ABERTO, não bloqueante — não impede uso de nenhuma das duas
fontes; é um item de limpeza de duplicação de código entre branches.

**Descrição:** ao implementar o subconjunto CFTC da Issue #14 nesta
sessão, ficou evidente que `usda_agtransport/client.py` (Issue #20, PR
#29, ainda não mesclada) e o novo `cftc_cot/client.py` implementavam a
mesma lógica de cliente Socrata/SODA de forma duplicada — ambas as fontes
usam a mesma plataforma. Foi extraído `socrata_connector/` como pacote
compartilhado (mesmo molde de `ckan_connector`, Issue #19), e `cftc_cot`
foi migrado para consumi-lo. `usda_agtransport/client.py` **não foi
editado**, porque isso exigiria alterar uma branch de PR de outra sessão
ainda em revisão, sem coordenação — fora do escopo autorizado desta
execução.

**Como desbloquear:** quando a PR #29 (AgTransport) for revisada/mesclada,
migrar `usda_agtransport` para consumir `socrata_connector` em vez do
`SocrataClient` que ainda duplica a mesma lógica naquela branch.

**Impacto:** nenhum — ambas as implementações funcionam de forma
independente e correta hoje; é só uma segunda implementação do mesmo
protocolo coexistindo temporariamente até a consolidação.

---

## 2026-08-15 — Issue #15: Copernicus CDS (ERA5/AgERA5) e NASA FIRMS exigem chave nova

**Status:** ABERTO, não bloqueante — bloqueia só duas das seis fontes
candidatas da Issue #15; NASA POWER (a quinta) foi implementada nesta
sessão sem depender deste blocker.

**Descrição:** as fontes candidatas da Issue #15 foram testadas
diretamente (chamada HTTP real, sem chave quando possível) antes de
decidir o que implementar:

- Copernicus Climate Data Store (ERA5/AgERA5,
  `https://cds.climate.copernicus.eu/api`): o endpoint raiz responde
  `HTTP 202` com mensagem de boas-vindas sem chave, mas a documentação
  oficial do CDS exige token pessoal (UID + API key, registro gratuito)
  para qualquer requisição de dados real — não confirmado nesta sessão
  porque exigiria criar conta.
- NASA FIRMS (`firms.modaps.eosdis.nasa.gov/api/area/csv/DEMO_KEY/...`):
  `HTTP 400` — `"Invalid MAP_KEY"`. Diferente de outras APIs da NASA,
  `DEMO_KEY` não é aceito; exige `MAP_KEY` pessoal via registro gratuito.

Ambas exigem "chave nova" no sentido da regra de Fase D ("fontes que não
exijam compra/chave nova") e ficam fora do escopo desta rodada. Evidência
completa em `docs/sources/nasa_power/README.md` (seção "Fontes da Issue
#15 fora do escopo desta avaliação").

**Como desbloquear:** usuário decide se registra as chaves/tokens
necessários (ambos têm registro gratuito por e-mail) e onde armazená-los
com segurança (nunca em texto plano no Git, conforme `CLAUDE.md`). Só
então retomar a avaliação dessas duas fontes dentro da Issue #15.

**Impacto:** Issue #15 permanece parcialmente atendida — NASA POWER
implementado e enviado (PR #33); as outras cinco fontes candidatas
(Copernicus, ANA HidroWebService, NASA FIRMS, NOAA/USGS Water, USACE
Rivergages) aguardam decisão humana sobre credenciais, descoberta de
endpoint ou simplesmente não têm relevância geográfica para o MT — ver
próximo item.

---

## 2026-08-15 — Issue #15: endpoint de série temporal do ANA HidroWebService não localizado

**Status:** ABERTO, não bloqueante — não é bloqueio de credencial, é
pendência de descoberta de endpoint.

**Descrição:** o serviço de inventário legado do ANA HidroWebService
(`telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroInventario`) responde sem
chave e retorna XML real com estações do Mato Grosso quando filtrado por
`nmEstado=MATO GROSSO`. Já o endpoint mais novo testado para série de
cotas (`www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/
HidroinfoanaSerieCotas/v1`) respondeu `HTTP 404` — o caminho exato da API
de série da ANA não foi confirmado nesta sessão (a API da ANA já trocou
de rota mais de uma vez segundo documentação pública).

**Como desbloquear:** em uma execução futura, mapear a documentação
oficial atualizada da ANA (ou testar variações de caminho) para
encontrar o endpoint de série correspondente ao inventário já confirmado;
só então avaliar hidrologia MT-específica como extensão da Issue #15.

**Impacto:** nenhum sobre o NASA POWER implementado nesta sessão — a
avaliação de hidrologia MT-específica (rios navegáveis relevantes para
logística) fica pendente para uma rodada futura de Fase D.

---

## 2026-08-15 — Inconsistência documental pré-existente: `AGENTS.md` referencia `docs/OBSIDIAN_SECOND_BRAIN.md` inexistente

**Status:** ABERTO, informativo — não bloqueia nenhuma frente de
engenharia, encontrado incidentalmente pela revisão Codex da Issue #15,
não introduzido por esta sessão.

**Descrição:** `AGENTS.md` referencia `docs/OBSIDIAN_SECOND_BRAIN.md`,
mas o arquivo existente no repositório é `docs/OBSIDIAN.md`. Não
investigado a fundo nesta sessão (fora do escopo da Issue #15/branch
`feat/15-nasa-power-poc`, que parte de `main` sem tocar `AGENTS.md`).

**Como desbloquear:** confirmar em uma execução futura se `docs/OBSIDIAN.md`
é o arquivo correto (e `AGENTS.md` precisa de correção) ou se
`docs/OBSIDIAN_SECOND_BRAIN.md` deveria existir e falta ser criado/migrado
— possivelmente relacionado à Issue #26 (Segundo Cérebro/Obsidian),
trabalhada pelo worker KNOWLEDGE em paralelo nesta mesma janela 48h
(`improve/issue-26-knowledge-48h`), não pelo worker ENGINEERING.

**Impacto:** nenhum sobre o código desta sessão; risco de confusão para
quem seguir a referência de `AGENTS.md` até existir correção.

**Atualização em 2026-08-15 (execução 7):** confirmado, sem editar nada
nesta branch, que o worker KNOWLEDGE já corrigiu essa referência em
`AGENTS.md` (linha 12: `docs/OBSIDIAN.md`, não
`docs/OBSIDIAN_SECOND_BRAIN.md`) na branch `improve/issue-26-knowledge-48h`
(commits locais ainda não enviados a `origin` no momento da checagem).
Nenhuma ação adicional necessária deste lado — evitar duplicar a correção;
revalidar apenas se essa branch for mesclada/enviada e a referência em
`main` continuar quebrada.
