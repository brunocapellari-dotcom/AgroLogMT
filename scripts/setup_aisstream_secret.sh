#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
SA_NAME="${SA_NAME:-agrolog-collector}"
SECRET_NAME="${SECRET_NAME:-aisstream-api-key}"
REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
command -v gcloud >/dev/null || { echo 'ERRO: gcloud ausente' >&2; exit 2; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || {
  echo 'ERRO: nenhuma conta gcloud ativa' >&2; exit 2;
}

gcloud services enable secretmanager.googleapis.com --project "$PROJECT_ID" >/dev/null

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "ERRO: service account não existe: $SA_EMAIL" >&2
  exit 2
fi

printf 'AISStream API key (não será exibida): '
IFS= read -rs AIS_KEY
printf '\n'
if [[ -z "$AIS_KEY" ]]; then
  echo 'ERRO: chave vazia' >&2
  exit 2
fi

if ! gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud secrets create "$SECRET_NAME" --replication-policy=automatic --project "$PROJECT_ID" >/dev/null
fi
printf '%s' "$AIS_KEY" | gcloud secrets versions add "$SECRET_NAME" --data-file=- --project "$PROJECT_ID" >/dev/null

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

# Limpeza best-effort de cópia legada. A credencial operacional tem uma única
# origem: Secret Manager. GitHub Actions apenas dispara o Cloud Run Job.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  gh secret delete AISSTREAM_API_KEY --repo "$REPO" >/dev/null 2>&1 || true
fi
unset AIS_KEY

echo "OK: segredo ${SECRET_NAME} configurado somente no Google Secret Manager para ${SA_EMAIL}."
