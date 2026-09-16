#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
MERCADO_DATASET="${MERCADO_DATASET:-mercado}"
HIDRO_DATASET="${HIDRO_DATASET:-hidrologia}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-}"
DRIVE_FOLDER_SECRET="${DRIVE_FOLDER_SECRET:-agrolog-drive-folder-id}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-p0-$(date +%Y%m%d%H%M%S)}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
ANA_IDENTIFICADOR_SECRET="${ANA_IDENTIFICADOR_SECRET:-agrolog-ana-identificador}"
ANA_SENHA_SECRET="${ANA_SENHA_SECRET:-agrolog-ana-senha}"
MANAGE_SCHEDULER="${MANAGE_SCHEDULER:-0}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERRO: projeto GCP ausente" >&2
  exit 2
fi
if [[ "$MANAGE_SCHEDULER" != "0" ]]; then
  echo "ERRO: deploy P0 não administra Cloud Scheduler. Use o bootstrap/administração canônica." >&2
  exit 2
fi
for cmd in gcloud bq; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done

gcloud config set project "$PROJECT_ID" >/dev/null
if [[ -z "$DRIVE_FOLDER_ID" ]]; then
  DRIVE_FOLDER_ID="$(gcloud secrets versions access latest --secret "$DRIVE_FOLDER_SECRET" --project "$PROJECT_ID" 2>/dev/null || true)"
fi
if [[ -z "$DRIVE_FOLDER_ID" ]]; then
  echo "ERRO: referência RAW ausente. Configure ${DRIVE_FOLDER_SECRET} no bootstrap administrativo." >&2
  exit 2
fi

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SERVICE_ACCOUNT:-${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
PTAX_JOB="agrolog-ptax"
ANA_JOB="agrolog-ana-hidro"

require_api() {
  local api="$1"
  gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api" || {
    echo "ERRO: API $api não habilitada; execute scripts/setup_github_gcp_wif.sh." >&2
    exit 3
  }
}

require_dataset() {
  local dataset="$1" tmp actual
  tmp="/tmp/agrolog-p0-${dataset}.json"
  if ! bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${dataset}" >"$tmp" 2>/dev/null; then
    echo "ERRO: dataset ${dataset} ausente; execute o bootstrap administrativo." >&2
    exit 3
  fi
  actual="$(python - "$tmp" <<'PY'
import json,sys
print(json.load(open(sys.argv[1], encoding='utf-8')).get('location',''))
PY
)"
  if [[ -n "$actual" && "$actual" != "$BQ_LOCATION" ]]; then
    echo "ERRO: dataset ${dataset} em ${actual}; esperado ${BQ_LOCATION}" >&2
    exit 3
  fi
}

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com storage.googleapis.com secretmanager.googleapis.com; do
  require_api "$api"
done
for sa in "$COLLECTOR_SERVICE_ACCOUNT" "$BUILD_SERVICE_ACCOUNT"; do
  gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1 || {
    echo "ERRO: service account ausente: $sa; execute o bootstrap administrativo." >&2
    exit 3
  }
done
for dataset in "$OPS_DATASET" "$MERCADO_DATASET" "$HIDRO_DATASET"; do
  require_dataset "$dataset"
done
gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: Artifact Registry ${AR_REPOSITORY} ausente." >&2
  exit 3
}
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: staging bucket ${BUILD_SOURCE_BUCKET} ausente." >&2
  exit 3
}

# Mesmo build canônico do collector; nenhuma IAM/API/dataset é criada aqui.
gcloud builds submit . \
  --project "$PROJECT_ID" \
  --service-account "$BUILD_SERVICE_ACCOUNT" \
  --gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source" \
  --config collector/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_MERCADO_DATASET=${MERCADO_DATASET},AGROLOG_HIDRO_DATASET=${HIDRO_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.p0.json"

gcloud run jobs deploy "$PTAX_JOB" \
  --image "$IMAGE" --region "$REGION" --project "$PROJECT_ID" \
  --service-account "$COLLECTOR_SERVICE_ACCOUNT" \
  --set-env-vars "${common_env},AGROLOG_GROUP=dados,AGROLOG_SOURCE_ID=bcb_ptax_usd_daily" \
  --max-retries 1 --task-timeout 10m

ANA_READY=true
for secret in "$ANA_IDENTIFICADOR_SECRET" "$ANA_SENHA_SECRET"; do
  if ! gcloud secrets describe "$secret" --project "$PROJECT_ID" >/dev/null 2>&1; then
    ANA_READY=false
  fi
done

if [[ "$ANA_READY" == "true" ]]; then
  gcloud run jobs deploy "$ANA_JOB" \
    --image "$IMAGE" --region "$REGION" --project "$PROJECT_ID" \
    --service-account "$COLLECTOR_SERVICE_ACCOUNT" \
    --set-env-vars "${common_env},AGROLOG_GROUP=dados,AGROLOG_SOURCE_ID=ana_hidroweb_m04_stations" \
    --set-secrets "ANA_IDENTIFICADOR=${ANA_IDENTIFICADOR_SECRET}:latest,ANA_SENHA=${ANA_SENHA_SECRET}:latest" \
    --max-retries 1 --task-timeout 30m
else
  echo "ANA_NOT_DEPLOYED: secrets canônicos ausentes; PTAX foi implantada normalmente." >&2
fi

unset DRIVE_FOLDER_ID common_env

cat <<EOF
P0 deploy concluído sobre infraestrutura pré-provisionada.
image=${IMAGE}
ptax_job=${PTAX_JOB}
ana_job=$([[ "$ANA_READY" == "true" ]] && echo "$ANA_JOB" || echo "NOT_DEPLOYED_SECRETS_MISSING")
ptax_table=${PROJECT_ID}.${MERCADO_DATASET}.ptax_usd_daily
hydro_table=${PROJECT_ID}.${HIDRO_DATASET}.hydro_station_telemetry
scheduler=UNCHANGED_BY_DEPLOY

Homologação PTAX:
gcloud run jobs execute ${PTAX_JOB} --region ${REGION} --project ${PROJECT_ID} --wait
python scripts/backfill_ptax_2026.py
python scripts/build_market_freshness_views.py

Homologação ANA (quando secrets existirem):
gcloud run jobs execute ${ANA_JOB} --region ${REGION} --project ${PROJECT_ID} --wait
python scripts/backfill_m04_ana.py --start 2023-01-01
python scripts/build_m04_hydro_views.py
EOF
