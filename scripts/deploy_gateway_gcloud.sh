#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
MARITIME_DATASET="${MARITIME_DATASET:-agrolog_models}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
IMAGE_NAME="${IMAGE_NAME:-gateway}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
SERVICE_NAME="${SERVICE_NAME:-agrolog-gateway}"
MAX_INSTANCES="${GATEWAY_MAX_INSTANCES:-3}"
CONCURRENCY="${GATEWAY_CONCURRENCY:-20}"
REQUEST_TIMEOUT="${GATEWAY_REQUEST_TIMEOUT:-60}"
MEMORY="${GATEWAY_MEMORY:-512Mi}"
CPU="${GATEWAY_CPU:-1}"
BQ_MAX_BYTES_BILLED="${AGROLOG_BQ_MAX_BYTES_BILLED:-1000000000}"
BQ_QUERY_TIMEOUT_SECONDS="${AGROLOG_BQ_QUERY_TIMEOUT_SECONDS:-30}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
for cmd in gcloud bq; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done
for value in "$MAX_INSTANCES" "$CONCURRENCY" "$REQUEST_TIMEOUT" "$BQ_MAX_BYTES_BILLED" "$BQ_QUERY_TIMEOUT_SECONDS"; do
  [[ "$value" =~ ^[0-9]+$ ]] || { echo "ERRO: limite numérico inválido: $value" >&2; exit 2; }
done
[[ "$MAX_INSTANCES" -ge 1 && "$MAX_INSTANCES" -le 20 ]] || { echo "ERRO: GATEWAY_MAX_INSTANCES fora do limite 1..20" >&2; exit 2; }
[[ "$CONCURRENCY" -ge 1 && "$CONCURRENCY" -le 100 ]] || { echo "ERRO: GATEWAY_CONCURRENCY fora do limite 1..100" >&2; exit 2; }
[[ "$REQUEST_TIMEOUT" -ge 5 && "$REQUEST_TIMEOUT" -le 120 ]] || { echo "ERRO: GATEWAY_REQUEST_TIMEOUT fora do limite 5..120" >&2; exit 2; }
[[ "$BQ_MAX_BYTES_BILLED" -ge 1000000 ]] || { echo "ERRO: AGROLOG_BQ_MAX_BYTES_BILLED baixo/inválido" >&2; exit 2; }
[[ "$BQ_QUERY_TIMEOUT_SECONDS" -ge 1 && "$BQ_QUERY_TIMEOUT_SECONDS" -le 120 ]] || { echo "ERRO: timeout BigQuery inválido" >&2; exit 2; }

GATEWAY_SERVICE_ACCOUNT="${GATEWAY_SERVICE_ACCOUNT:-${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

gcloud config set project "$PROJECT_ID" >/dev/null

assert_private_gateway() {
  if ! gcloud run services describe "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
    return 0
  fi
  local broad_binding runtime_sa
  broad_binding="$(gcloud run services get-iam-policy "$SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter='bindings.role=roles/run.invoker AND (bindings.members=allUsers OR bindings.members=allAuthenticatedUsers)' \
    --format='value(bindings.members)' | head -n1)"
  if [[ "$broad_binding" == "allUsers" || "$broad_binding" == "allAuthenticatedUsers" ]]; then
    echo "ERRO: ${SERVICE_NAME} possui invocação ampla (${broad_binding}) com roles/run.invoker." >&2
    exit 4
  fi
  runtime_sa="$(gcloud run services describe "$SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" \
    --format='value(spec.template.spec.serviceAccountName)')"
  if [[ -n "$runtime_sa" && "$runtime_sa" != "$GATEWAY_SERVICE_ACCOUNT" ]]; then
    echo "ERRO: ${SERVICE_NAME} usa service account inesperada: ${runtime_sa}; esperado ${GATEWAY_SERVICE_ACCOUNT}." >&2
    exit 4
  fi
}

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com storage.googleapis.com; do
  gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api" || {
    echo "ERRO: API $api não habilitada. Execute o bootstrap administrativo." >&2
    exit 3
  }
done
for sa in "$GATEWAY_SERVICE_ACCOUNT" "$BUILD_SERVICE_ACCOUNT"; do
  gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1 || {
    echo "ERRO: service account ausente: $sa. Execute o bootstrap administrativo." >&2
    exit 3
  }
done
for dataset in "$LOGISTICA_DATASET" "$MARITIME_DATASET"; do
  bq show --project_id="$PROJECT_ID" "${PROJECT_ID}:${dataset}" >/dev/null 2>&1 || {
    echo "ERRO: dataset ${dataset} ausente. Execute o bootstrap administrativo." >&2
    exit 3
  }
done
gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: Artifact Registry ${AR_REPOSITORY} ausente." >&2
  exit 3
}
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: staging bucket ${BUILD_SOURCE_BUCKET} ausente." >&2
  exit 3
}

assert_private_gateway

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
  --execution-environment gen2 \
  --cpu "$CPU" \
  --memory "$MEMORY" \
  --max-instances "$MAX_INSTANCES" \
  --concurrency "$CONCURRENCY" \
  --timeout "${REQUEST_TIMEOUT}s" \
  --set-env-vars "AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_LOGISTICA_DATASET=${LOGISTICA_DATASET},AGROLOG_MARITIME_DATASET=${MARITIME_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_BQ_MAX_BYTES_BILLED=${BQ_MAX_BYTES_BILLED},AGROLOG_BQ_QUERY_TIMEOUT_SECONDS=${BQ_QUERY_TIMEOUT_SECONDS},AGROLOG_ENABLE_DOCS=0"

assert_private_gateway

echo "Gateway implantado: privado, identidade dedicada e limites de recurso verificados."
echo "Runtime identity: ${GATEWAY_SERVICE_ACCOUNT}"
echo "Max instances: ${MAX_INSTANCES}; concurrency: ${CONCURRENCY}; timeout: ${REQUEST_TIMEOUT}s"
echo "BigQuery maximum bytes billed: ${BQ_MAX_BYTES_BILLED}; query timeout: ${BQ_QUERY_TIMEOUT_SECONDS}s"
echo "Maritime UI: /maritime/"
echo "Dataset Maritime: ${PROJECT_ID}.${MARITIME_DATASET}"
echo "Build staging: gs://${BUILD_SOURCE_BUCKET}"
echo "IAM, APIs e datasets permanecem responsabilidade do bootstrap administrativo."
