#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
MARITIME_DATASET="${MARITIME_DATASET:-agrolog_models}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-gateway}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
SERVICE_NAME="${SERVICE_NAME:-agrolog-gateway}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Nenhum projeto GCP configurado. Execute: gcloud config set project SEU_PROJECT_ID" >&2
  exit 2
fi

GATEWAY_SERVICE_ACCOUNT="${GATEWAY_SERVICE_ACCOUNT:-${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
STORAGE_TABLE="${PROJECT_ID}:${LOGISTICA_DATASET}.armazens_conab"
MARITIME_TABLES=(
  "shipping_lineup_calls"
  "shipping_ais_positions"
  "shipping_port_operations"
  "shipping_reconciliation"
)

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com iam.googleapis.com

if ! gcloud iam service-accounts describe "${GATEWAY_SERVICE_ACCOUNT}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${GATEWAY_SA_NAME}" --display-name "AgroLog Gateway"
fi

# Executa queries no projeto; leitura de dados continua concedida por tabela.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${GATEWAY_SERVICE_ACCOUNT}" \
  --role="roles/bigquery.jobUser" \
  --condition=None >/dev/null

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}"
fi

gcloud builds submit . \
  --config gateway/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

# CONAB permanece com leitura no menor escopo possível.
if bq show "${STORAGE_TABLE}" >/dev/null 2>&1; then
  bq add-iam-policy-binding \
    --member="serviceAccount:${GATEWAY_SERVICE_ACCOUNT}" \
    --role="roles/bigquery.dataViewer" \
    --table=true \
    "${STORAGE_TABLE}"
else
  echo "Aviso: tabela ainda ausente, permissao nao aplicada: ${STORAGE_TABLE}" >&2
fi

# Maritime V1 expõe somente as quatro tabelas canônicas necessárias ao mapa/replay/reconciliação.
for table_name in "${MARITIME_TABLES[@]}"; do
  table_ref="${PROJECT_ID}:${MARITIME_DATASET}.${table_name}"
  if bq show "${table_ref}" >/dev/null 2>&1; then
    bq add-iam-policy-binding \
      --member="serviceAccount:${GATEWAY_SERVICE_ACCOUNT}" \
      --role="roles/bigquery.dataViewer" \
      --table=true \
      "${table_ref}"
  else
    echo "Aviso: tabela Maritime ainda ausente, permissao nao aplicada: ${table_ref}" >&2
  fi
done

gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --service-account "${GATEWAY_SERVICE_ACCOUNT}" \
  --no-allow-unauthenticated \
  --set-env-vars "AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_LOGISTICA_DATASET=${LOGISTICA_DATASET},AGROLOG_MARITIME_DATASET=${MARITIME_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION}"

echo "Gateway implantado com autenticação obrigatória: ${SERVICE_NAME}"
echo "Maritime UI incorporada em /maritime/"
echo "Para teste local autenticado: gcloud run services proxy ${SERVICE_NAME} --region ${REGION} --port 8080"
echo "Depois acesse: http://localhost:8080/maritime/"
