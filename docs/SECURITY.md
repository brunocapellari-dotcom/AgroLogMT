# Segurança do AgroLog MT

Este documento é a fonte canônica para segurança de informação, identidade, segredos, CI/CD, runtime, acesso e ingestão de dados do AgroLog MT. Ele complementa `docs/ARCHITECTURE.md`, `docs/DATA_GOVERNANCE.md` e `docs/REPOSITORY_GOVERNANCE.md`.

## 1. Princípios obrigatórios

1. **Least privilege** — cada identidade recebe somente permissões necessárias.
2. **Fail closed** — ausência de autenticação, secret, hash, lineage ou gate obrigatório bloqueia a operação.
3. **Zero long-lived credentials in code/CI** — GitHub Actions usa WIF/OIDC; chaves JSON de service account são proibidas.
4. **Single operational secret origin** — credenciais e referências operacionais sensíveis consumidas pelo runtime GCP ficam no Secret Manager.
5. **Segregation of duties** — bootstrap administrativo altera IAM/APIs/datasets; deploy recorrente não amplia privilégio.
6. **Immutability/provenance** — RAW relevante preserva bytes originais, hash e metadados suficientes para auditoria.
7. **Minimization** — coletar, persistir, logar e expor somente o necessário.
8. **Controlled supply chain** — dependências/Actions reproduzíveis, revisáveis e imutáveis quando possível.
9. **No direct database exposure** — consumidores usam identidades dedicadas e interfaces controladas.
10. **Privileged changes are auditable** — IAM, secrets, WIF, exposição e retenção exigem evidência/readback.
11. **External data is untrusted by default** — autenticidade da origem não implica integridade sem validação.
12. **Recovery must be tested** — backup sem teste de restore não é controle operacional comprovado.
13. **Public repository means public history** — commits, metadados, Issues e PRs alcançáveis devem ser tratados como informação pública; remover um valor da árvore atual não remove o histórico Git.

## 2. Classificação de segurança

A classe de segurança é independente da classe epistemológica (`observado`, `estimado`, `projetado`, `inferido` etc.).

- `PUBLIC`: publicação deliberadamente pública.
- `INTERNAL`: uso interno; divulgação externa não autorizada por padrão.
- `CONFIDENTIAL`: informação comercial/operacional/contratual cujo vazamento pode causar dano.
- `RESTRICTED`: tokens, cookies, passwords, chaves, PII direta, segredo ou material protegido por obrigação específica.

`RESTRICTED` nunca entra no GitHub, logs, artifacts de CI, prompts reutilizáveis ou dashboards gerais. PII deve ser minimizada/pseudonimizada quando identidade não for necessária.

## 3. Identidades e IAM

Identidades canônicas:

- `agrolog-github-deployer` — CI/CD federado e validação final;
- `agrolog-builder` — Cloud Build;
- `agrolog-collector` — runtime de coleta;
- `agrolog-gateway` — runtime de leitura;
- `agrolog-scheduler` — invocação de jobs agendados, sem escrita analítica ou administração.

Regras:

- não usar default service account para workloads do AgroLog;
- não conceder `Owner`, `Editor` ou `bigquery.admin` a runtimes;
- preferir grants em dataset/recurso;
- remover bindings legados excessivos;
- IAM fica fora do deploy recorrente;
- service-account key é proibida salvo exceção formal, temporária e auditada;
- scheduler recebe somente capacidade de invocar os jobs autorizados e não cria/altera datasets, IAM ou dados.

## 4. GitHub Actions e WIF

- `permissions` explícito e mínimo em todo workflow;
- `id-token: write` somente em jobs que realmente autenticam no GCP;
- Actions remotas pinadas por SHA completo;
- PRs não recebem secrets de produção;
- `pull_request_target` com checkout de código não confiável é proibido;
- WIF restringe por `repository_id`, `repository_owner_id` e `refs/heads/main` para credencial de produção;
- provider existente deve ser reconciliado, não apenas criado;
- nenhum fallback para chave JSON;
- artifact/output não contém token, cookie, password, authorization header ou payload `RESTRICTED`;
- `main` deve exigir PR/checks, bloquear force-push/deleção e impedir bypass rotineiro;
- fork/PR público jamais é autoridade de deploy; produção só é acessada pelo job manual final autenticado e restrito a `main`.

## 5. Segredos e referências operacionais

Origem preferencial: Google Secret Manager.

- ANA, AISStream e futuras credenciais operacionais ficam no Secret Manager;
- a referência da pasta RAW fica no Secret Manager como `agrolog-drive-folder-id`, em vez de default hard-coded no GitHub;
- GitHub Secrets guarda somente metadados inevitáveis de federação/deploy, não cópia conveniente de credencial de fonte;
- secrets não são passados em command line quando houver secret mount/env seguro;
- exception/log não deve serializar objeto contendo secret;
- collectors aplicam redaction defensiva a mensagens de erro, sem substituir a proibição de logar segredo;
- suspeita de exposição exige revogação/rotação e invalidação de versões antigas;
- identificador de recurso que não seja segredo ainda deve ser minimizado quando sua publicação não traz benefício técnico.

## 6. Git, arquivos locais e build context

Proibido versionar ou copiar para imagem:

- `.env*` reais;
- `*.key`, `*.pem`, `*.p12`, `*.pfx`;
- chaves SSH privadas;
- credenciais Google/service account;
- `.npmrc`, `.pypirc`, kubeconfig com token;
- RAW real, planilhas operacionais/cliente;
- dump de banco ou Terraform state com segredo.

`.gitignore`, `.dockerignore`, scanner próprio, Gitleaks e revisão são camadas complementares. Antes de mudança para visibilidade pública, a árvore atual e o histórico completo precisam passar varredura de segredos; caso um segredo histórico seja encontrado, a primeira ação é revogar/rotacionar, não apenas apagar o arquivo atual.

## 7. Containers e Cloud Run

- containers rodam non-root quando suportado;
- imagem contém somente runtime necessário;
- credenciais nunca são copiadas para imagem;
- Gateway exige IAM e não aceita `allUsers` ou `allAuthenticatedUsers` como invoker amplo;
- cada serviço/job usa service account dedicada;
- deploy verifica identidade e exposição após mudança;
- logs não registram query sensível, auth header ou body por padrão;
- CORS em produção usa allowlist explícita.

## 8. BigQuery, RAW, normalized e curated

O fluxo padrão é:

`UNTRUSTED EXTERNAL → RAW/QUARANTINE → VALIDATION/SANITIZATION → NORMALIZED → QUALITY GATE → CURATED`

Regras:

- BigQuery permanece fonte única de verdade analítica;
- RAW preserva hash/referência ao original quando aplicável;
- normalized preserva transformação e lineage;
- curated recebe somente registros que passaram gate;
- runtime escreve apenas nos datasets necessários;
- Gateway lê somente datasets publicados;
- `CONFIDENTIAL/RESTRICTED` exige revisão de acesso antes da ingestão;
- Drive/Cloud Storage usa menor permissão suficiente;
- programação, forecast ou ausência de fonte nunca vira observado.

## 9. Segurança de fontes e API spoofing

Antes de uma fonte ser `active`:

- endpoint/domínio deve ser identificado e, quando possível, allowlisted;
- transporte remoto deve usar TLS (`https`/`wss`), salvo exceção formal de fonte oficial sem alternativa;
- redirects devem ser limitados/controlados quando o client permitir;
- credenciais ficam separadas do endpoint e payload;
- certificado/TLS não pode ser desabilitado (`verify=False`, `-k` ou equivalente são proibidos em produção);
- content type, tamanho, schema e semântica esperada devem ser verificados;
- hash/signature/checksum oficial deve ser conferido quando a fonte publicar mecanismo verificável;
- mudança súbita de host, formato, certificate chain ou volume pode bloquear promoção até revisão.

`collector/source_registry.py` rejeita fonte `active` com transporte remoto inseguro e mantém `planned/gated` fora do scheduler.

## 10. Arquivos maliciosos e archive bombs

Arquivos externos não são confiáveis mesmo quando originados de domínio conhecido.

Controles:

- limite explícito de payload antes da persistência/promocão;
- ZIP inspecionado antes de extração;
- path traversal (`../`), path absoluto e symlink em archive são bloqueados;
- limitar quantidade de membros, tamanho descompactado e compression ratio;
- PDF/documento não executa JavaScript, macro, attachment ou ação incorporada;
- XLS/XLSX é tratado como dado; macro não é executada;
- formato inesperado ou assinatura incompatível com content type entra em quarantine/blocked;
- nenhum arquivo externo é executado como código/plugin.

Primitives atuais: `collector/input_security.py`.

## 11. CSV/Spreadsheet injection

O AgroLog deve preservar o valor canônico no RAW/normalized. Na **superfície de exportação** para CSV/XLSX aberto por software de planilha, strings iniciadas por `=`, `+`, `-` ou `@` devem ser neutralizadas para impedir formula injection.

Não alterar silenciosamente o valor analítico armazenado para resolver um risco que pertence à camada de apresentação/exportação.

Helper atual: `neutralize_spreadsheet_cell`.

## 12. Prompt injection por notícias/documentos

Notícia, PDF, planilha, página, e-mail, áudio transcrito ou outro material externo é **evidência**, nunca instrução de agente.

Regras obrigatórias:

- envelopar conteúdo externo com `trust_class=UNTRUSTED_EXTERNAL` antes de uso por IA;
- instruções presentes dentro do conteúdo não alteram system/developer prompt, ferramentas, IAM, secrets, workflow ou policy;
- conteúdo suspeito de prompt injection recebe flag e pode exigir revisão humana/auditoria;
- agentes recebem ferramentas por allowlist, não por texto recuperado;
- RAG/Obsidian retorna evidência + provenance, não comandos executáveis;
- um documento não pode solicitar exfiltração de segredo, chamada de ferramenta, edição de sistema ou execução shell;
- o AUDITOR AI deve poder bloquear síntese material com evidência contaminada ou não rastreável.

`assess_untrusted_text` é detector heurístico complementar; não é prova de segurança isolada.

## 13. Data poisoning e quebra de fonte

Uma fonte autenticada pode publicar dado errado, corrompido ou estruturalmente alterado. Quality gates devem observar, conforme o domínio:

- row-count/tie-out;
- duplicidade;
- missingness;
- ranges/unidades;
- cardinalidade de dimensões;
- mudança de schema;
- salto de distribuição/nível incompatível com histórico;
- variação abrupta de coverage;
- consistência entre fontes independentes quando houver cross-check legítimo;
- vintage/revisão esperada;
- source health e freshness.

Anomalia não é corrigida automaticamente por valor “plausível”. O dado fica `WARN/BLOCKED` até evidência suficiente.

## 14. Supply chain de software

- dependências diretas versionadas; runtime crítico deve evoluir para lock/hash reproduzível;
- Node usa lockfile + `npm ci` quando lockfile canônico existir;
- install scripts arbitrários são evitados;
- dependência nova exige revisão de licença, origem, manutenção e risco;
- Actions remotas usam SHA completo;
- Dependabot/scanner é controle complementar;
- imagens/base images devem ser atualizadas por PR e testadas, nunca automaticamente promovidas ao runtime sem gate;
- pacote abandonado/comprometido pode ser removido sem alterar fonte de verdade dos dados.

## 15. Segurança de aplicação

- identificador SQL usa allowlist/normalização; valores usam query parameters;
- endpoints limitam cardinalidade/janela;
- erros públicos não expõem SQL/stack/secret/estrutura sensível;
- logs usam correlation/request IDs e metadados mínimos;
- collectors têm timeout e limites de payload;
- Gateway permanece read-only por padrão;
- tool/action de agente deve ter input schema, escopo e autorização explícita.

## 16. Backup, restore e retenção

Antes de declarar recuperação operacional:

- BigQuery datasets/tabelas críticas devem ter estratégia documentada de recuperação/snapshot/export quando aplicável;
- RAW imutável deve ter política de retenção adequada à licença e necessidade de auditoria;
- configuração GitHub permanece versionada e protegida;
- secrets têm rotação/recuperação administrativa sem armazenar plaintext fora do vault;
- Obsidian/Segundo Cérebro deve possuir backup versionado/replicado compatível com sua classificação de segurança;
- restore deve ser testado em ambiente isolado e registrar data, escopo, RPO/RTO observado e resultado;
- backup que nunca foi restaurado permanece `UNVERIFIED`.

## 17. Audit logs e observabilidade

Registrar sem segredo:

- run/source/status/freshness;
- hash e lineage;
- row counts/gates;
- identidade de runtime/deploy;
- mudança de IAM/WIF/secret policy via mecanismos cloud/GitHub;
- request IDs do Gateway;
- falhas de autenticação, schema drift e security gate;
- decisão de promoção/bloqueio.

Cloud Audit Logs/GitHub logs complementam os manifests e tabelas `agrolog_ops`; nenhum deles sozinho substitui lineage analítico.

## 18. Gate antes de produção

Uma mudança só é promovida quando aplicável:

1. CI integral executou no mesmo SHA e está verde;
2. workflow YAML válido e permissions mínimas;
3. Actions pinadas por SHA;
4. nenhum secret/RAW no diff e scan do histórico completo aprovado no release final;
5. container non-root;
6. IAM least privilege verificado;
7. serviço privado sem invoker amplo;
8. source transport/auth verificados;
9. hostile-input gates aplicáveis passaram;
10. persistência fecha schema/row-count/tie-out/freshness;
11. logs/evidências não contêm `RESTRICTED`;
12. backup/restore tem status explícito quando o módulo exigir recuperação operacional.

Se o CI nem recebe runner, o estado é `CI_EXECUTION_BLOCKER`, não “teste verde” nem “falha funcional”. Visibilidade pública pode aumentar a disponibilidade de GitHub-hosted runners, mas nunca substitui o gate; após qualquer mudança de visibilidade, o gate integral deve ser reexecutado no SHA exato antes de merge/release.

## 19. Resposta a incidente

Em suspeita de vazamento, poisoning ou acesso indevido:

1. bloquear/limitar caminho afetado;
2. preservar evidência necessária à investigação;
3. revogar/rotacionar secrets/tokens quando aplicável;
4. revisar Cloud Audit Logs/GitHub/manifestos/source health;
5. identificar dados/recursos e intervalo afetados;
6. quarentenar vintages/curated contaminados sem apagar RAW necessário à auditoria;
7. corrigir a causa;
8. revalidar IAM/WIF/source/runtime/pipeline antes de reativar;
9. registrar impacto, decisão e prevenção.

Nunca publicar segredo em issue/PR/log durante investigação.

## 20. Exceções

Toda exceção registra necessidade, escopo, risco, responsável, expiração, controles compensatórios e critério de remoção. Exceção temporária nunca vira arquitetura permanente automaticamente.
