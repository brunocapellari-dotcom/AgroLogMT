# AgroLog MT — CI self-hosted efêmero no Google Cloud

## Decisão canônica

O repositório pode permanecer **privado**. GitHub-hosted minutes não são requisito para a release final.

Os gates pesados usam runners self-hosted efêmeros no Google Compute Engine com o label:

`agrolog-ci`

GitHub Actions continua sendo o orquestrador do CI/CD. A computação é fornecida pelo GCP.

## Princípios

- runner de uso único (`--ephemeral`);
- nenhuma service account GCP anexada à VM;
- acesso GCP do job somente por GitHub OIDC / Workload Identity Federation;
- Secure Boot, vTPM e integrity monitoring;
- pacote oficial `actions/runner` validado pelo digest SHA-256 publicado no release;
- sem cache hospedado do GitHub no gate final;
- nenhum segredo de fonte de produção em GitHub Actions;
- containers e testes rodam na VM; produção continua em Cloud Run/BigQuery/Secret Manager;
- VM deve ser excluída após o job pelo cleanup ou pelo limite máximo de execução.

## Provisionamento

No Cloud Shell, com `gcloud` e `gh` autenticados e projeto GCP correto:

```bash
cd ~/AgroLogMT
git fetch origin
git switch release/final-project-gate-v1
git pull --ff-only
bash scripts/create_gce_ephemeral_runner.sh
```

Um runner executa um job. Para a homologação final, que possui dois jobs sequenciais, criar dois runners:

```bash
RUNNER_COUNT=2 MAX_RUN_DURATION=3h bash scripts/create_gce_ephemeral_runner.sh
```

Depois:

```bash
bash scripts/cleanup_gce_ci_runners.sh
```

## Visibilidade pública

Tornar o repositório público **não é requisito** para obter capacidade de execução.

Antes de qualquer mudança futura para público são gates obrigatórios:

1. Gitleaks no histórico Git completo = PASS;
2. nenhum segredo antigo, credencial, dado restrito ou artefato privado no histórico;
3. logs e artifacts revisados;
4. proteção de `main` ativa;
5. PRs de forks não podem executar em runner self-hosted privilegiado;
6. revisão explícita das licenças e dos dados distribuíveis.

Até esses gates passarem, `AgroLogMT` permanece privado.

## Escala futura

Para 1–2 jobs simultâneos, o script GCE efêmero é preferível pela simplicidade e menor superfície operacional.

Se a demanda crescer para muitos runners concorrentes, avaliar `terraform-google-modules/terraform-google-github-actions-runners` (Managed Instance Groups ou GKE/Actions Runner Controller). Não introduzir GKE/ARC antes de existir necessidade mensurável; isso criaria custo e complexidade sem ganho atual.

## Release policy

Não existe promoção por módulo. O único gate de release é `full-project-final-gate.yml`, que executa o projeto inteiro. O workflow `unit-tests.yml` é diagnóstico manual e não substitui o gate canônico.
