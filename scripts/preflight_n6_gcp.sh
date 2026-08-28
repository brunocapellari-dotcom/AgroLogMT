#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-agrolog-github-deployer}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"

failures=0
warnings=0
ok() { printf 'OK   %s\n' "$*"; }
warn() { printf 'WARN %s\n' "$*"; warnings=$((warnings+1)); }
fail() { printf 'FAIL %s\n' "$*"; failures=$((failures+1)); }

command -v gcloud >/dev/null 2>&1 || { echo 'gcloud ausente' >&2; exit 2; }
command -v bq >/dev/null 2>&1 || { echo 'bq ausente' >&2; exit 2; }
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo 'Projeto GCP não configurado.' >&2
  exit 2
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] && ok "conta ativa: $ACTIVE_ACCOUNT" || fail 'nenhuma conta gcloud ativa'
ok "projeto: $PROJECT_ID"
ok "região Cloud Run: $REGION"
ok "localização BigQuery esperada: $BQ_LOCATION"

for api in \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  bigquery.googleapis.com drive.googleapis.com iam.googleapis.com storage.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com logging.googleapis.com; do
  if gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api"; then
    ok "API habilitada: $api"
  else
    fail "API não habilitada: $api"
  fi
done

for dataset in "$OPS_DATASET" "$LOGISTICA_DATASET" "$TRADE_DATASET"; do
  tmp="/tmp/agrolog-dataset-${dataset}.json"
  if bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${dataset}" >"$tmp" 2>/dev/null; then
    actual_location="$(python - "$tmp" <<'PY'
import json,sys
print(json.load(open(sys.argv[1])).get('location',''))
PY
)"
    if [[ -n "$actual_location" && "$actual_location" != "$BQ_LOCATION" ]]; then
      fail "dataset ${dataset} está em ${actual_location}, esperado ${BQ_LOCATION}"
    else
      ok "dataset existente: ${dataset} (${actual_location:-localização não informada})"
    fi
  else
    fail "dataset obrigatório ausente: ${dataset}; execute o bootstrap administrativo"
  fi
done

for name in "$DEPLOYER_SA_NAME" "$BUILD_SA_NAME" "$COLLECTOR_SA_NAME" "$GATEWAY_SA_NAME"; do
  sa="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  if gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1; then
    ok "service account existe: $sa"
  else
    fail "service account obrigatória ausente: $sa"
  fi
done

if gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Artifact Registry: $AR_REPOSITORY"
else
  fail "Artifact Registry ausente: $AR_REPOSITORY"
fi
if gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Build staging bucket: gs://${BUILD_SOURCE_BUCKET}"
else
  fail "Build staging bucket ausente: gs://${BUILD_SOURCE_BUCKET}"
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
