#!/usr/bin/env bash
set -euo pipefail

# One-time bootstrap for AgroLogMT GitHub Actions -> Google Cloud without service-account JSON keys.
# Run from Google Cloud Shell (or a machine with authenticated gcloud + gh).
# ANA credentials are read silently and sent directly to GitHub Actions secrets; they are never printed.

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
POOL_ID="${POOL_ID:-github}"
PROVIDER_ID="${PROVIDER_ID:-agrologmt}"
SA_NAME="${SA_NAME:-agrolog-collector}"

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
  artifactregistry.googleapis.com --project "$PROJECT_ID"

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" --display-name="AgroLog collector"
fi

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
    --attribute-condition="assertion.repository=='${REPO}'"
fi

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}"

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --project "$PROJECT_ID" \
  --role='roles/iam.workloadIdentityUser' \
  --member="$PRINCIPAL" >/dev/null

# GitHub Actions secrets for WIF. No JSON service-account key is created.
printf '%s' "$PROVIDER_RESOURCE" | gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "$REPO"
printf '%s' "$SA_EMAIL" | gh secret set GCP_SERVICE_ACCOUNT --repo "$REPO"
printf '%s' "$PROJECT_ID" | gh secret set GCP_PROJECT_ID --repo "$REPO"

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

echo
printf 'OK: GitHub Actions configurado para GCP via Workload Identity Federation.\n'
printf 'OK: credenciais ANA armazenadas como GitHub Actions secrets.\n'
printf 'Próximo teste: gh workflow run operational-models-readiness.yml --repo %s\n' "$REPO"
