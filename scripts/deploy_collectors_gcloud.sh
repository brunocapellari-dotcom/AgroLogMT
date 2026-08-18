#!/usr/bin/env bash
set -euo pipefail

required=(PROJECT_ID REGION COLLECTOR_SERVICE_ACCOUNT SCHEDULER_SERVICE_ACCOUNT DRIVE_FOLDER_ID)
for var in "${required[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Variavel obrigatoria ausente: $var" >&2
    exit 2
  fi
done

OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
TIME_ZONE="${TIME_ZONE:-America/Campo_Grande}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
run_api="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com cloudscheduler.googleapis.com bigquery.googleapis.com drive.googleapis.com

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}"
fi

gcloud builds submit --tag "${IMAGE}" .

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.pilot.json"

for group in radar dados conhecimento; do
  job="agrolog-${group}"
  gcloud run jobs deploy "${job}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --service-account "${COLLECTOR_SERVICE_ACCOUNT}" \
    --set-env-vars "${common_env},AGROLOG_GROUP=${group}" \
    --max-retries 1 \
    --task-timeout 30m
done

declare -A schedules=(
  [radar]="0 */2 * * *"
  [dados]="0 */4 * * *"
  [conhecimento]="0 * * * *"
)

for group in radar dados conhecimento; do
  scheduler="agrolog-${group}-schedule"
  uri="${run_api}/agrolog-${group}:run"
  if gcloud scheduler jobs describe "${scheduler}" --location "${REGION}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${scheduler}" \
      --location "${REGION}" \
      --schedule "${schedules[$group]}" \
      --time-zone "${TIME_ZONE}" \
      --uri "${uri}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  else
    gcloud scheduler jobs create http "${scheduler}" \
      --location "${REGION}" \
      --schedule "${schedules[$group]}" \
      --time-zone "${TIME_ZONE}" \
      --uri "${uri}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  fi
done

echo "Deploy concluido. Antes do primeiro job, confirme que DRIVE_FOLDER_ID foi compartilhada como Editor com ${COLLECTOR_SERVICE_ACCOUNT}."
echo "Teste manual: gcloud run jobs execute agrolog-dados --region ${REGION} --wait"
