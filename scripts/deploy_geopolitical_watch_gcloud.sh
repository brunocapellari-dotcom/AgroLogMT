#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
INTELLIGENCE_DATASET="${INTELLIGENCE_DATASET:-agrolog_intelligence}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"
JOB_NAME="${JOB_NAME:-agrolog-geopolitical-watch}"
SCHEDULER_NAME="${SCHEDULER_NAME:-agrolog-geopolitical-watch-schedule}"
SCHEDULE="${SCHEDULE:-5 * * * *}"
TIME_ZONE="${TIME_ZONE:-America/Cuiaba}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Nenhum projeto GCP configurado. Defina PROJECT_ID ou execute gcloud config set project." >&2
  exit 2
fi
if [[ -z "${DRIVE_FOLDER_ID}" ]]; then
  echo "Defina DRIVE_FOLDER_ID para a pasta RAW compartilhada com a service account do coletor." >&2
  exit 2
fi

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SERVICE_ACCOUNT:-${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
SCHEDULER_SERVICE_ACCOUNT="${SCHEDULER_SERVICE_ACCOUNT:-${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}:run"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com bigquery.googleapis.com drive.googleapis.com iam.googleapis.com

if ! gcloud iam service-accounts describe "${COLLECTOR_SERVICE_ACCOUNT}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${COLLECTOR_SA_NAME}" --display-name "AgroLog Collector"
fi
if ! gcloud iam service-accounts describe "${SCHEDULER_SERVICE_ACCOUNT}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SCHEDULER_SA_NAME}" --display-name "AgroLog Scheduler Invoker"
fi

gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}" --role="roles/bigquery.user" --condition=None >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SCHEDULER_SERVICE_ACCOUNT}" --role="roles/run.invoker" --condition=None >/dev/null

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}"
fi

gcloud builds submit --tag "${IMAGE}" .

ENV_VARS="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_INTELLIGENCE_DATASET=${INTELLIGENCE_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_GEOPOLITICAL_CONFIG=/app/collector/config/sources.geopolitical.example.json"

gcloud run jobs deploy "${JOB_NAME}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --service-account "${COLLECTOR_SERVICE_ACCOUNT}" \
  --command python \
  --args=-m,collector.geopolitical_cloud_runner \
  --set-env-vars "${ENV_VARS}" \
  --max-retries 1 \
  --task-timeout 20m

if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location "${REGION}" \
    --schedule "${SCHEDULE}" \
    --time-zone "${TIME_ZONE}" \
    --uri "${RUN_URI}" \
    --http-method POST \
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
else
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location "${REGION}" \
    --schedule "${SCHEDULE}" \
    --time-zone "${TIME_ZONE}" \
    --uri "${RUN_URI}" \
    --http-method POST \
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
fi

cat <<EOF
Geopolitical Watch preparado para execucao horaria.
Job: ${JOB_NAME}
Scheduler: ${SCHEDULER_NAME}
Dataset analitico: ${INTELLIGENCE_DATASET}

Antes do primeiro teste, confirme que a pasta Drive ${DRIVE_FOLDER_ID} esta compartilhada como Editor com:
${COLLECTOR_SERVICE_ACCOUNT}

Teste manual:
gcloud run jobs execute ${JOB_NAME} --region ${REGION} --wait
EOF
