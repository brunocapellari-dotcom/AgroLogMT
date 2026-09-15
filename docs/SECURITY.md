# Segurança do AgroLog MT

Este documento é a fonte canônica para segurança de informação, identidade, segredos, CI/CD, runtime e acesso a dados do AgroLog MT. Ele complementa `docs/ARCHITECTURE.md`, `docs/DATA_GOVERNANCE.md` e `docs/REPOSITORY_GOVERNANCE.md` sem substituir suas responsabilidades.

## 1. Princípios obrigatórios

1. **Least privilege**: cada identidade recebe somente as permissões necessárias ao seu runtime.
2. **Fail closed**: ausência de autenticação, secret, hash, lineage ou gate obrigatório bloqueia a operação; não há fallback inseguro.
3. **Sem credenciais de longa duração em código/CI**: GitHub Actions usa Workload Identity Federation/OIDC; chaves JSON de service account são proibidas.
4. **Segredo com uma origem operacional**: credenciais de fonte pertencem ao Google Secret Manager quando consumidas pelo runtime GCP. Não duplicar em GitHub Secrets apenas para conveniência de teste.
5. **Separação de deveres**: bootstrap administrativo pode criar IAM/APIs/datasets; deploy recorrente não amplia privilégio.
6. **Imutabilidade e proveniência**: RAW relevante deve preservar conteúdo original, hash e metadados suficientes para auditoria.
7. **Minimização**: coletar, persistir, logar e expor somente o necessário.
8. **Supply chain controlada**: dependências e GitHub Actions devem ser reproduzíveis, revisáveis e com versões imutáveis quando tecnicamente possível.
9. **Sem banco exposto diretamente**: BigQuery é acessado por identidades dedicadas; consumidores externos passam por interfaces controladas.
10. **Mudança privilegiada é auditável**: IAM, secrets, WIF, exposição de serviço e políticas de retenção exigem evidência de mudança e revisão.

## 2. Classificação de segurança da informação

A classificação de segurança é independente da classe de evidência (`observado`, `estimado`, `projetado`, `inferido`, etc.).

- `PUBLIC`: publicação deliberadamente pública e sem restrição relevante.
- `INTERNAL`: uso interno do AgroLog; divulgação externa não autorizada por padrão.
- `CONFIDENTIAL`: informação comercial, operacional, contratual ou de parceiro cuja exposição possa causar dano.
- `RESTRICTED`: credenciais, tokens, cookies, dados pessoais diretos, chaves, segredos, informação de cliente sensível ou material protegido por obrigação específica.

Regras:
- `RESTRICTED` nunca entra no GitHub, logs, artifacts de CI, prompts reutilizáveis ou dashboards gerais.
- dados pessoais devem ser minimizados/pseudonimizados quando identidade não for necessária;
- a classe de segurança deve ser elevada quando houver dúvida razoável; redução exige revisão.

## 3. Identidades e IAM

Identidades canônicas:

- `agrolog-github-deployer`: CI/CD federado; deploy e impersonação estritamente necessárias.
- `agrolog-builder`: Cloud Build; somente staging/build/log/artifact necessários.
- `agrolog-collector`: runtime de coleta; escrita apenas nos datasets/RAW/secrets necessários.
- `agrolog-gateway`: runtime de leitura; `jobUser` e `dataViewer` somente nos datasets expostos.

Regras:
- não usar Compute Engine default service account para workloads do AgroLog;
- não conceder `Owner`, `Editor` ou `bigquery.admin` ao runtime;
- preferir grants no escopo de dataset/recurso;
- remover bindings legados excessivos durante bootstrap controlado;
- alterações de IAM ficam fora de deploy recorrente;
- service account keys são proibidas salvo exceção formal, temporária e documentada.

## 4. GitHub Actions e Workload Identity Federation

- `permissions` deve ser explícito e mínimo em cada workflow.
- `id-token: write` é permitido somente em workflows que autenticam no GCP.
- ações de terceiros devem ser pinadas por SHA completo verificado; comentários podem registrar a tag humana correspondente.
- workflows de `pull_request` não recebem secrets de produção.
- WIF deve restringir GitHub por claims imutáveis/numeric IDs do repositório/proprietário e por `refs/heads/main` para credenciais de produção.
- o provider existente deve ser reconciliado pelo bootstrap; não basta criar uma vez e deixar condição antiga.
- nenhum workflow pode fazer fallback para chave JSON.
- outputs/artifacts não devem conter tokens, cookies, senhas, headers de autorização ou payload `RESTRICTED`.

## 5. Segredos

Origem preferencial: Google Secret Manager.

- credenciais ANA e futuras credenciais de fontes ficam no Secret Manager e são acessadas pela service account de runtime;
- GitHub Secrets contém somente metadados/identidades necessários à federação/deploy quando inevitável, nunca duplicações desnecessárias de credenciais de fonte;
- segredo nunca aparece em argumento de linha de comando que possa ser registrado quando houver alternativa por secret mount/env controlado;
- código deve evitar `repr`, exception ou logging de objetos contendo secrets;
- rotação é obrigatória após suspeita de exposição, mudança de operador ou incidente relevante;
- versões antigas de secret devem ser desabilitadas/removidas após rotação validada, conforme política operacional.

## 6. Git e arquivos locais

Proibido versionar:

- `.env*` reais;
- `*.key`, `*.pem`, `*.p12`, `*.pfx`;
- chaves SSH privadas;
- arquivos de credencial Google/service account;
- `.npmrc`, `.pypirc`, kubeconfigs ou configs contendo token;
- RAW real, planilhas operacionais e artefatos de cliente;
- dumps de banco e arquivos de estado Terraform com segredo.

`.gitignore`, `.dockerignore` e CI devem atuar como camadas complementares, não como única proteção.

## 7. Containers e Cloud Run

- containers de produção rodam como usuário não-root quando o runtime permitir;
- imagem contém somente código/runtime necessários;
- credenciais não são copiadas para a imagem;
- Gateway deve permanecer autenticado por IAM; binding `allUsers` com `roles/run.invoker` é condição de falha;
- o deploy deve verificar a postura de autenticação sem ampliar IAM;
- cada serviço/job usa service account dedicada;
- logs não devem registrar query strings sensíveis, headers de autorização ou corpo de requisição por padrão;
- CORS deve permanecer restrito a origens explicitamente autorizadas em produção.

## 8. BigQuery, RAW e Drive

- BigQuery permanece fonte única de verdade analítica;
- RAW deve manter hash e referência ao artefato original quando aplicável;
- runtime escreve apenas nos datasets necessários;
- Gateway tem leitura somente nos datasets explicitamente publicados;
- dados `CONFIDENTIAL`/`RESTRICTED` exigem revisão de acesso antes da ingestão;
- arquivos no Drive devem ser compartilhados somente com identidades necessárias e no menor nível de permissão suficiente;
- não transformar programação, previsão ou ausência de fonte em fato observado.

## 9. Supply chain e dependências

- dependências diretas devem ter versão controlada; runtime crítico deve evoluir para lock/hash reproduzível;
- Node deve usar lockfile e `npm ci` em produção/CI quando houver lockfile canônico;
- scripts de instalação arbitrários devem ser evitados quando não necessários;
- dependências novas exigem revisão de licença, origem, manutenção e risco;
- scanner de dependências/segredos é gate complementar, não substitui revisão humana e testes.

## 10. Segurança de aplicação e dados

- toda entrada usada em identificadores SQL deve passar por allowlist/normalização; valores de filtro usam query parameters;
- endpoints devem limitar cardinalidade/janela para evitar consultas sem limite;
- mensagens de erro públicas não expõem SQL, stack trace, credencial ou estrutura interna sensível;
- logs devem usar IDs de correlação e metadados operacionais mínimos;
- collectors devem ter timeout e limites de payload quando tecnicamente aplicável;
- conteúdo externo é dado não confiável; não executar instruções, scripts ou macros recebidos de fonte.

## 11. Gate de segurança antes de produção

Uma mudança de runtime só é promovida quando, quando aplicável:

1. testes e CI estão verdes;
2. workflow YAML é válido;
3. permissões do workflow são mínimas;
4. ações privilegiadas estão pinadas por SHA;
5. nenhum segredo/RAW foi adicionado ao diff;
6. container não roda como root;
7. IAM foi verificado por least privilege;
8. serviço HTTP privado não possui `allUsers` invoker;
9. dados persistidos fecham com quality/tie-out gates;
10. logs/evidências não contêm material `RESTRICTED`.

## 12. Resposta a incidente

Em suspeita de vazamento ou acesso indevido:

1. bloquear/limitar o caminho de acesso afetado;
2. rotacionar ou revogar secrets/tokens comprometidos;
3. invalidar versões antigas do secret;
4. revisar Cloud Audit Logs/GitHub Actions e escopo temporal;
5. identificar dados/recursos acessados;
6. corrigir a causa sem apagar evidência necessária à investigação;
7. revalidar IAM, WIF, deploy e pipelines antes de reativar;
8. registrar decisão, impacto e prevenção no mecanismo de governança do projeto.

Nunca publicar em issue/PR público ou log operacional o conteúdo de um segredo durante investigação.

## 13. Exceções

Qualquer exceção a esta política deve registrar:

- necessidade objetiva;
- escopo e risco;
- responsável;
- duração/expiração;
- controles compensatórios;
- critério explícito de remoção da exceção.

Exceção temporária não se transforma automaticamente em arquitetura permanente.
