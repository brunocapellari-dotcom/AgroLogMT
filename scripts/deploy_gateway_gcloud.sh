#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
MARITIME_DATASET="${MARITIME_DATASET:-agrolog_models}"
PECUARIA_DATASET="${PECUARIA_DATASET:-pecuaria}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
IMAGE_NAME="${IMAGE_NAME:-gateway}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
SERVICE_NAME="${SERVICE_NAME:-agrolog-gateway}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
for cmd in gcloud bq; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done

GATEWAY_SERVICE_ACCOUNT="${GATEWAY_SERVICE_ACCOUNT:-${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

gcloud config set project "$PROJECT_ID" >/dev/null

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com storage.googleapis.com; do
  gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api" || {
    echo "ERRO: API $api não habilitada. Execute scripts/setup_github_gcp_wif.sh com identidade administradora." >&2
    exit 3
  }
done
for sa in "$GATEWAY_SERVICE_ACCOUNT" "$BUILD_SERVICE_ACCOUNT"; do
  gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1 || {
    echo "ERRO: service account ausente: $sa. Execute o bootstrap administrativo." >&2
    exit 3
  }
done
for dataset in "$LOGISTICA_DATASET" "$MARITIME_DATASET" "$PECUARIA_DATASET" "$TRADE_DATASET"; do
  bq show --project_id="$PROJECT_ID" "${PROJECT_ID}:${dataset}" >/dev/null 2>&1 || {
    echo "ERRO: dataset ${dataset} ausente. Execute o bootstrap administrativo apropriado." >&2
    exit 3
  }
done
gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: Artifact Registry ${AR_REPOSITORY} ausente. Execute o bootstrap administrativo." >&2
  exit 3
}
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: staging bucket ${BUILD_SOURCE_BUCKET} ausente. Execute o bootstrap administrativo." >&2
  exit 3
}

gcloud builds submit . \
  --project "$PROJECT_ID" \
  --service-account "$BUILD_SERVICE_ACCOUNT" \
  --gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source" \
  --config gateway/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$GATEWAY_SERVICE_ACCOUNT" \
  --set-env-vars "AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_LOGISTICA_DATASET=${LOGISTICA_DATASET},AGROLOG_MARITIME_DATASET=${MARITIME_DATASET},AGROLOG_PECUARIA_DATASET=${PECUARIA_DATASET},AGROLOG_TRADE_DATASET=${TRADE_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_TRADE_CODES_CONTRACT=/app/contracts/product_trade_codes.v1.json"

echo "Gateway implantado; autenticação obrigatória é governada pelo bootstrap administrativo."
echo "Maritime UI preservada em /maritime/"
echo "Datasets: logística=${LOGISTICA_DATASET}, maritime=${MARITIME_DATASET}, pecuária=${PECUARIA_DATASET}, trade=${TRADE_DATASET}"
echo "Build staging: gs://${BUILD_SOURCE_BUCKET}"
echo "IAM, APIs e permissões BigQuery permanecem responsabilidade do bootstrap administrativo."
