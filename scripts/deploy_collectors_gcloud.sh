#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-17AX2iCrQ17Jm86Pp9ijqn3hyEHVaQPqd}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
AGRO_DATASET="${AGRO_DATASET:-agro}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
RAW_BUCKET="${RAW_BUCKET:-${PROJECT_ID}-agrolog-raw}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
MANAGE_SCHEDULER="${MANAGE_SCHEDULER:-0}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
if [[ "$MANAGE_SCHEDULER" != "0" ]]; then
  echo "ERRO: deploy recorrente não gerencia Cloud Scheduler/IAM. Use bootstrap administrativo separado." >&2
  exit 2
fi
for cmd in gcloud bq; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SERVICE_ACCOUNT:-${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
BUILD_SERVICE_ACCOUNT_RESOURCE="${BUILD_SERVICE_ACCOUNT_RESOURCE:-projects/${PROJECT_ID}/serviceAccounts/${BUILD_SERVICE_ACCOUNT}}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

gcloud config set project "$PROJECT_ID" >/dev/null

require_api() {
  local api="$1"
  gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api" || {
    echo "ERRO: API $api não habilitada. Execute scripts/setup_github_gcp_wif.sh com identidade administradora." >&2
    exit 3
  }
}

require_dataset() {
  local dataset="$1"
  local tmp actual
  tmp="/tmp/agrolog-dataset-${dataset}.json"
  if ! bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${dataset}" >"$tmp" 2>/dev/null; then
    echo "ERRO: dataset ${dataset} ausente. Bootstrap administrativo obrigatório." >&2
    exit 3
  fi
  actual="$(python - "$tmp" <<'PY'
import json,sys
print(json.load(open(sys.argv[1])).get('location',''))
PY
)"
  if [[ -n "$actual" && "$actual" != "$BQ_LOCATION" ]]; then
    echo "ERRO: dataset ${dataset} em ${actual}; esperado ${BQ_LOCATION}" >&2
    exit 3
  fi
}

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com storage.googleapis.com; do
  require_api "$api"
done
for sa in "$COLLECTOR_SERVICE_ACCOUNT" "$BUILD_SERVICE_ACCOUNT"; do
  gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1 || {
    echo "ERRO: service account ausente: $sa. Execute o bootstrap administrativo." >&2
    exit 3
  }
done
for dataset in "$OPS_DATASET" "$LOGISTICA_DATASET" "$TRADE_DATASET" "$AGRO_DATASET"; do
  require_dataset "$dataset"
done
gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: Artifact Registry ${AR_REPOSITORY} ausente. Execute o bootstrap administrativo." >&2
  exit 3
}
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: staging bucket ${BUILD_SOURCE_BUCKET} ausente. Execute o bootstrap administrativo." >&2
  exit 3
}
gcloud storage buckets describe "gs://${RAW_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: RAW bucket ${RAW_BUCKET} ausente. Execute scripts/setup_raw_gcs.sh." >&2
  exit 3
}

# Cloud Build API exige o nome canônico do recurso da service account.
# Mantemos BUILD_SERVICE_ACCOUNT como e-mail para IAM/gcloud describe e derivamos
# o resource name somente para o campo serviceAccount do build.
gcloud builds submit . \
  --project "$PROJECT_ID" \
  --service-account "$BUILD_SERVICE_ACCOUNT_RESOURCE" \
  --gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source" \
  --config collector/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_LOGISTICA_DATASET=${LOGISTICA_DATASET},AGROLOG_TRADE_DATASET=${TRADE_DATASET},AGROLOG_AGRO_DATASET=${AGRO_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_RAW_BACKEND=gcs,AGROLOG_RAW_BUCKET=${RAW_BUCKET},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.pilot.json"

for group in radar dados conhecimento; do
  job="agrolog-${group}"
  gcloud run jobs deploy "$job" \
    --image "$IMAGE" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --service-account "$COLLECTOR_SERVICE_ACCOUNT" \
    --set-env-vars "${common_env},AGROLOG_GROUP=${group}" \
    --max-retries 1 \
    --task-timeout 30m
done

cat <<EOF
Collector atualizado sem mutação de IAM/APIs/datasets.
Projeto: ${PROJECT_ID}
Região: ${REGION}
Imagem: ${IMAGE}
Builder: ${BUILD_SERVICE_ACCOUNT}
Build staging: gs://${BUILD_SOURCE_BUCKET}
Collector: ${COLLECTOR_SERVICE_ACCOUNT}
Datasets: ${OPS_DATASET}, ${LOGISTICA_DATASET}, ${TRADE_DATASET}, ${AGRO_DATASET}
RAW operacional: gs://${RAW_BUCKET}
Drive de referência/arquivos autorizados: ${DRIVE_FOLDER_ID}

O RAW operacional usa GCS porque service accounts não possuem quota própria no My Drive.
Drive permanece disponível apenas para entradas autorizadas e fluxos humanos.

Homologação controlada CONAB:
gcloud run jobs execute agrolog-dados --region ${REGION} --project ${PROJECT_ID} --wait --update-env-vars "AGROLOG_SOURCE_ID=conab_armazens_cadastrados"
python scripts/validate_conab_n6.py --project ${PROJECT_ID}

Homologação controlada ComexStat:
gcloud run jobs execute agrolog-dados --region ${REGION} --project ${PROJECT_ID} --wait --update-env-vars "AGROLOG_CONFIG=/app/collector/config/sources.p0.json,AGROLOG_SOURCE_ID=mdic_comexstat_soja_mt_export_api,AGROLOG_TRADE_DATASET=${TRADE_DATASET}"
EOF
