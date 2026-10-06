# Execução contínua — Drive + BigQuery + Cloud Run

Este documento descreve a execução persistente canônica do AgroLog MT. A regra central é separar **bootstrap administrativo** de **deploy recorrente**.

## Arquitetura

`Fonte → Source Registry/config → Cloud Run Job → CollectorEngine → RAW autorizado + BigQuery → validação → AgroLog Gateway`

Responsabilidades:

- `scripts/setup_github_gcp_wif.sh`: única rotina administrativa de bootstrap para APIs, service accounts, datasets, IAM, WIF, Artifact Registry, staging bucket e segredos canônicos;
- `scripts/deploy_collectors_gcloud.sh`: build/deploy dos collectors e do job Pecuária, sem criar IAM, APIs ou datasets;
- `scripts/deploy_p0_connectors_gcloud.sh`: deploy dos workloads P0 sobre a mesma infraestrutura pré-provisionada, sem administrar IAM, APIs, datasets ou Cloud Scheduler;
- `scripts/deploy_gateway_gcloud.sh`: build/deploy do Gateway privado sobre infraestrutura pré-provisionada;
- `.github/workflows/full-project-final-gate.yml`: autoridade única de CI/release integral.

## Persistência

- armazenamento RAW autorizado: artefatos originais com hash/proveniência;
- BigQuery `agrolog_ops`: estado, manifests, auditoria e metadados operacionais;
- datasets temáticos: somente conforme fontes reais entram em produção;
- GitHub: código, contratos, configuração, SQL, testes e documentação — nunca RAW real ou credenciais.

## Referência da pasta RAW

O identificador da pasta RAW **não deve ficar hard-coded no repositório público**.

Fonte canônica em runtime:

`Secret Manager: agrolog-drive-folder-id`

O bootstrap aceita `DRIVE_FOLDER_ID` apenas como entrada administrativa ou, quando possível, migra o valor já implantado em `agrolog-dados` para o Secret Manager. O valor não deve ser ecoado em logs.

O deploy lê o segredo com a identidade federada/deployer e injeta `AGROLOG_DRIVE_FOLDER_ID` nos jobs. O collector recebe somente o valor necessário ao runtime.

## Bootstrap administrativo

Executar com identidade humana administradora autenticada:

```bash
PROJECT_ID=<projeto> DRIVE_FOLDER_ID=<id-da-pasta-raw> bash scripts/setup_github_gcp_wif.sh
```

O bootstrap é idempotente e centraliza:

- APIs Google Cloud necessárias;
- WIF/OIDC GitHub → GCP sem chave JSON;
- service accounts dedicadas de deploy, build, collector, gateway e scheduler;
- datasets e localização BigQuery;
- permissões mínimas por identidade;
- Artifact Registry e bucket de staging;
- `agrolog-drive-folder-id` no Secret Manager;
- credenciais ANA no Secret Manager quando configuradas.

Depois do bootstrap, compartilhar a pasta RAW como Editor **somente** com a service account do collector indicada pelo script.

## Deploy dos collectors

```bash
bash scripts/deploy_collectors_gcloud.sh
```

O script falha fechado quando algum pré-requisito estiver ausente ou em região incorreta. Ele não corrige IAM criando privilégios durante o deploy.

Jobs principais:

- `agrolog-radar`;
- `agrolog-dados`;
- `agrolog-conhecimento`;
- `agrolog-pecuaria` em Registry Mode.

## Deploy P0

```bash
bash scripts/deploy_p0_connectors_gcloud.sh
```

O P0 reutiliza a mesma imagem/infraestrutura canônica e pode implantar:

- PTAX;
- ANA/HidroWeb, somente quando os segredos canônicos estiverem disponíveis.

`MANAGE_SCHEDULER` permanece `0`: deploy recorrente não cria nem altera agendamentos. Administração de scheduler é responsabilidade do plano administrativo, não do deploy de workload.

## Google Drive

Google Cloud IAM não concede acesso ao My Drive. O compartilhamento da pasta RAW continua sendo um gate externo explícito.

A service account do collector deve ter apenas o acesso necessário à pasta autorizada; nenhum identificador da pasta, token ou credencial deve ser versionado no GitHub.

## Segurança para repositório público

Ao operar o AgroLog MT como repositório público:

- todo o histórico Git e Issues deve ser tratado como informação pública;
- nenhum segredo real deve existir em commits antigos ou atuais;
- `pull_request_target` com checkout de código não confiável é proibido;
- workflows de PR usam permissões mínimas e não recebem credenciais GCP;
- WIF é restrito por `repository_id`, `repository_owner_id` e `refs/heads/main`;
- deploy/release GCP só ocorre no gate manual final a partir de `main`;
- Gitleaks current-tree roda no gate determinístico e Gitleaks full-history no release final;
- branch/ruleset de `main` deve exigir o gate integral antes de merge.

## Validação

A versão só é considerada operacional quando o mesmo release candidato comprova:

- Full Project Final Gate determinístico;
- scan de segredos no histórico completo;
- dependências/workflows/containers em PASS;
- preflight GCP;
- homologação N6 completa;
- idempotência, data quality e temporalidade;
- Gateway E2E;
- restore drill;
- auditoria independente aplicável.

Documentação ou existência de scripts não substituem essas evidências.