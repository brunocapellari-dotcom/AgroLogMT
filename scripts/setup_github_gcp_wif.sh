#!/usr/bin/env bash
set -euo pipefail

# One-time bootstrap for AgroLogMT GitHub Actions -> Google Cloud without service-account JSON keys.
# Run from Google Cloud Shell (or a machine with authenticated gcloud + gh).
# The GitHub federated identity is a dedicated deployer account; the runtime collector remains low-privilege.

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
POOL_ID="${POOL_ID:-github}"
PROVIDER_ID="${PROVIDER_ID:-agrologmt}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-agrolog-github-deployer}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
CONFIGURE_ANA="${CONFIGURE_ANA:-0}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: configure o projeto: gcloud config set project <PROJECT_ID>" >&2
  exit 2
fi
command -v gcloud >/dev/null || { echo 'ERRO: gcloud ausente' >&2; exit 2; }
command -v gh >/dev/null || { echo 'ERRO: gh CLI ausente' >&2; exit 2; }

gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || {
  echo 'ERRO: nenhuma conta gcloud ativa' >&2; exit 2;
}
gh auth status >/dev/null 2>&1 || { echo 'ERRO: gh não autenticado; execute gh auth login' >&2; exit 2; }

echo "Projeto: $PROJECT_ID"
echo "Repo:    $REPO"

# APIs required by federation / current AgroLog deployment.
gcloud services enable \
  iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  bigquery.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com serviceusage.googleapis.com drive.googleapis.com \
  --project "$PROJECT_ID"

ensure_sa() {
  local name="$1"
  local display="$2"
  local email="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$email" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --project "$PROJECT_ID" --display-name="$display"
  fi
}

ensure_sa "$DEPLOYER_SA_NAME" "AgroLog GitHub deployer"
ensure_sa "$COLLECTOR_SA_NAME" "AgroLog collector runtime"

DEPLOYER_SA_EMAIL="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
COLLECTOR_SA_EMAIL="${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Bootstrap-only grants for the deployer. Runtime collector permissions remain dataset/service scoped
# and are configured by scripts/deploy_collectors_gcloud.sh.
DEPLOYER_ROLES=(
  roles/serviceusage.serviceUsageAdmin
  roles/iam.serviceAccountAdmin
  roles/iam.serviceAccountUser
  roles/resourcemanager.projectIamAdmin
  roles/run.admin
  roles/artifactregistry.admin
  roles/cloudbuild.builds.editor
  roles/storage.objectAdmin
  roles/bigquery.admin
)
for role in "${DEPLOYER_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${DEPLOYER_SA_EMAIL}" \
    --role="$role" \
    --condition=None >/dev/null
done

if ! gcloud iam workload-identity-pools describe "$POOL_ID" --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" --location=global --project "$PROJECT_ID" --display-name="GitHub Actions"
fi

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --workload-identity-pool="$POOL_ID" --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --workload-identity-pool="$POOL_ID" --location=global --project "$PROJECT_ID" \
    --display-name="AgroLogMT GitHub" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${REPO}' && assertion.ref=='refs/heads/main'"
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA_EMAIL" \
  --project "$PROJECT_ID" \
  --role='roles/iam.workloadIdentityUser' \
  --member="$PRINCIPAL" >/dev/null

# GitHub Actions secrets for WIF. No JSON service-account key is created.
printf '%s' "$PROVIDER_RESOURCE" | gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "$REPO"
printf '%s' "$DEPLOYER_SA_EMAIL" | gh secret set GCP_SERVICE_ACCOUNT --repo "$REPO"
printf '%s' "$DEPLOYER_SA_EMAIL" | gh secret set GCP_DEPLOYER_SERVICE_ACCOUNT --repo "$REPO"
printf '%s' "$PROJECT_ID" | gh secret set GCP_PROJECT_ID --repo "$REPO"

if [[ "$CONFIGURE_ANA" == "1" ]]; then
  printf 'ANA HidroWeb identificador: '
  IFS= read -r ANA_ID
  printf 'ANA HidroWeb senha (não será exibida): '
  IFS= read -rs ANA_PASSWORD
  printf '\n'
  if [[ -z "$ANA_ID" || -z "$ANA_PASSWORD" ]]; then
    echo 'ERRO: credenciais ANA não preenchidas.' >&2
    exit 2
  fi
  printf '%s' "$ANA_ID" | gh secret set ANA_HIDRO_IDENTIFICADOR --repo "$REPO"
  printf '%s' "$ANA_PASSWORD" | gh secret set ANA_HIDRO_SENHA --repo "$REPO"
  unset ANA_PASSWORD ANA_ID
fi

echo
printf 'OK: GitHub Actions configurado para GCP via Workload Identity Federation.\n'
printf 'Deployer federado: %s\n' "$DEPLOYER_SA_EMAIL"
printf 'Collector runtime:  %s\n' "$COLLECTOR_SA_EMAIL"
printf 'IMPORTANTE: compartilhe a pasta RAW do Drive como Editor com o Collector runtime antes da homologação completa.\n'
printf 'Próximo teste: gh workflow run operational-models-readiness.yml --repo %s -f mode=preflight\n' "$REPO"
printf 'Depois do preflight verde: gh workflow run operational-models-readiness.yml --repo %s -f mode=homologate\n' "$REPO"
