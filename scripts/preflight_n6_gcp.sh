#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"

failures=0
warnings=0

ok() { printf 'OK   %s\n' "$*"; }
warn() { printf 'WARN %s\n' "$*"; warnings=$((warnings+1)); }
fail() { printf 'FAIL %s\n' "$*"; failures=$((failures+1)); }

command -v gcloud >/dev/null 2>&1 || { echo 'gcloud ausente' >&2; exit 2; }
command -v bq >/dev/null 2>&1 || { echo 'bq ausente' >&2; exit 2; }

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo 'Projeto GCP não configurado.' >&2
  exit 2
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] && ok "conta ativa: $ACTIVE_ACCOUNT" || fail 'nenhuma conta gcloud ativa'
ok "projeto: $PROJECT_ID"
ok "região Cloud Run: $REGION"
ok "localização BigQuery esperada: $BQ_LOCATION"

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com drive.googleapis.com iam.googleapis.com; do
  if gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api"; then
    ok "API habilitada: $api"
  else
    fail "API não habilitada: $api"
  fi
done

for dataset in "$OPS_DATASET" "$LOGISTICA_DATASET"; do
  if bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${dataset}" >/tmp/agrolog-dataset.json 2>/dev/null; then
    actual_location="$(python - <<'PY'
import json
try:
    print(json.load(open('/tmp/agrolog-dataset.json')).get('location',''))
except Exception:
    print('')
PY
)"
    if [[ -n "$actual_location" && "$actual_location" != "$BQ_LOCATION" ]]; then
      fail "dataset ${dataset} está em ${actual_location}, esperado ${BQ_LOCATION}"
    else
      ok "dataset existente: ${dataset} (${actual_location:-localização não informada})"
    fi
  else
    warn "dataset ainda não existe: ${dataset}; deploy deverá criá-lo sob controle"
  fi
done

COLLECTOR_SA="${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GATEWAY_SA="${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
for sa in "$COLLECTOR_SA" "$GATEWAY_SA"; do
  if gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1; then
    ok "service account existe: $sa"
  else
    warn "service account ainda não existe: $sa"
  fi
done

if gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Artifact Registry: $AR_REPOSITORY"
else
  warn "Artifact Registry ainda não existe: $AR_REPOSITORY"
fi

for job in agrolog-dados agrolog-radar agrolog-conhecimento; do
  if gcloud run jobs describe "$job" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
    ok "Cloud Run Job existente: $job"
  else
    warn "Cloud Run Job ainda não implantado: $job"
  fi
done

if gcloud run services describe agrolog-gateway --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok 'Cloud Run service existente: agrolog-gateway'
else
  warn 'AgroLog Gateway ainda não implantado'
fi

printf '\nResumo: failures=%d warnings=%d\n' "$failures" "$warnings"
[[ "$failures" -eq 0 ]]
