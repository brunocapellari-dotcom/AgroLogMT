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

assert_private_gateway() {
  if ! gcloud run services describe "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
    return 0
  fi

  local public_binding runtime_sa
  public_binding="$(gcloud run services get-iam-policy "$SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter='bindings.role=roles/run.invoker AND bindings.members=allUsers' \
    --format='value(bindings.members)' | head -n1)"
  if [[ "$public_binding" == "allUsers" ]]; then
    echo "ERRO: ${SERVICE_NAME} possui allUsers com roles/run.invoker. Corrija no bootstrap administrativo antes de deploy." >&2
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
for dataset in "$LOGISTICA_DATASET" "$MARITIME_DATASET"; do
  bq show --project_id="$PROJECT_ID" "${PROJECT_ID}:${dataset}" >/dev/null 2>&1 || {
    echo "ERRO: dataset ${dataset} ausente. Execute o bootstrap administrativo." >&2
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

# Não mascarar exposição/identidade incorreta já existente com uma nova revisão.
assert_private_gateway

# Build com builder dedicado e staging exclusivo. IAM/datasets são responsabilidade do bootstrap.
gcloud builds submit . \
  --project "$PROJECT_ID" \
  --service-account "$BUILD_SERVICE_ACCOUNT" \
  --gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source" \
  --config gateway/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

# A exigência de autenticação é administrada no bootstrap. O deploy recorrente atualiza apenas a revisão.
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$GATEWAY_SERVICE_ACCOUNT" \
  --set-env-vars "AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_LOGISTICA_DATASET=${LOGISTICA_DATASET},AGROLOG_MARITIME_DATASET=${MARITIME_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION}"

# Verificação pós-deploy: falha fechada se a revisão resultar pública ou com identidade incorreta.
assert_private_gateway

echo "Gateway implantado e verificado como privado; autenticação obrigatória é governada pelo bootstrap administrativo."
echo "Runtime identity verificada: ${GATEWAY_SERVICE_ACCOUNT}"
echo "Maritime UI preservada em /maritime/"
echo "Dataset Maritime: ${PROJECT_ID}.${MARITIME_DATASET}"
echo "Build staging: gs://${BUILD_SOURCE_BUCKET}"
echo "IAM, APIs e permissões BigQuery permanecem responsabilidade do bootstrap administrativo."
echo "Para teste local autenticado: gcloud run services proxy ${SERVICE_NAME} --region ${REGION} --port 8080"
echo "Depois acesse: http://localhost:8080/maritime/"
