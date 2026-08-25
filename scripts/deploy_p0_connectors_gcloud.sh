#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
MERCADO_DATASET="${MERCADO_DATASET:-mercado}"
HIDRO_DATASET="${HIDRO_DATASET:-hidrologia}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-17AX2iCrQ17Jm86Pp9ijqn3hyEHVaQPqd}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-p0-$(date +%Y%m%d%H%M%S)}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"
ANA_IDENTIFICADOR_SECRET="${ANA_IDENTIFICADOR_SECRET:-agrolog-ana-identificador}"
ANA_SENHA_SECRET="${ANA_SENHA_SECRET:-agrolog-ana-senha}"
TIME_ZONE="${TIME_ZONE:-America/Cuiaba}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Projeto GCP ausente" >&2
  exit 2
fi

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SERVICE_ACCOUNT="${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
JOB="agrolog-p0"
SCHEDULER="agrolog-p0-hourly"
RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB}:run"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  bigquery.googleapis.com \
  drive.googleapis.com \
  iam.googleapis.com \
  secretmanager.googleapis.com

for account in "${COLLECTOR_SA_NAME}" "${SCHEDULER_SA_NAME}"; do
  email="${account}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "${email}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account}" --project "${PROJECT_ID}" --display-name "${account}"
  fi
done

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}" --role="roles/bigquery.user" --condition=None >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SCHEDULER_SERVICE_ACCOUNT}" --role="roles/run.invoker" --condition=None >/dev/null

ensure_dataset() {
  local dataset="$1"
  if ! bq show --project_id="${PROJECT_ID}" "${PROJECT_ID}:${dataset}" >/dev/null 2>&1; then
    bq --location="${BQ_LOCATION}" mk --dataset "${PROJECT_ID}:${dataset}"
  fi
  bq query --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" --use_legacy_sql=false --quiet \
    "GRANT \`roles/bigquery.dataEditor\` ON SCHEMA \`${PROJECT_ID}\`.${dataset} TO \"serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}\""
}

ensure_dataset "${OPS_DATASET}"
ensure_dataset "${MERCADO_DATASET}"
ensure_dataset "${HIDRO_DATASET}"

for secret in "${ANA_IDENTIFICADOR_SECRET}" "${ANA_SENHA_SECRET}"; do
  if ! gcloud secrets describe "${secret}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Secret obrigatório ausente: ${secret}" >&2
    echo "Crie o secret e adicione a versão fora do GitHub; o script nunca recebe o valor por argumento." >&2
    exit 4
  fi
  gcloud secrets add-iam-policy-binding "${secret}" --project "${PROJECT_ID}" \
    --member="serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}" --role="roles/secretmanager.secretAccessor" >/dev/null
done

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}" --project "${PROJECT_ID}"
fi

gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_MERCADO_DATASET=${MERCADO_DATASET},AGROLOG_HIDRO_DATASET=${HIDRO_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.p0.json,AGROLOG_GROUP=dados"

gcloud run jobs deploy "${JOB}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --service-account "${COLLECTOR_SERVICE_ACCOUNT}" \
  --set-env-vars "${common_env}" \
  --set-secrets "ANA_IDENTIFICADOR=${ANA_IDENTIFICADOR_SECRET}:latest,ANA_SENHA=${ANA_SENHA_SECRET}:latest" \
  --max-retries 1 \
  --task-timeout 30m

if gcloud scheduler jobs describe "${SCHEDULER}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "${SCHEDULER}" \
    --location "${REGION}" --project "${PROJECT_ID}" \
    --schedule "0 * * * *" --time-zone "${TIME_ZONE}" \
    --uri "${RUN_URI}" --http-method POST \
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
else
  gcloud scheduler jobs create http "${SCHEDULER}" \
    --location "${REGION}" --project "${PROJECT_ID}" \
    --schedule "0 * * * *" --time-zone "${TIME_ZONE}" \
    --uri "${RUN_URI}" --http-method POST \
    --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
fi

cat <<EOF
P0 deploy configurado.
job=${JOB}
image=${IMAGE}
ptax_table=${PROJECT_ID}.${MERCADO_DATASET}.ptax_usd_daily
hydro_table=${PROJECT_ID}.${HIDRO_DATASET}.hydro_station_telemetry

Execute homologação:
gcloud run jobs execute ${JOB} --region ${REGION} --project ${PROJECT_ID} --wait
bash scripts/validate_p0_connectors_gcloud.sh
EOF
