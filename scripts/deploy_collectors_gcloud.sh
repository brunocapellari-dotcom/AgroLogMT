#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-17AX2iCrQ17Jm86Pp9ijqn3hyEHVaQPqd}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
TIME_ZONE="${TIME_ZONE:-America/Cuiaba}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Nenhum projeto GCP configurado. Execute: gcloud config set project SEU_PROJECT_ID" >&2
  exit 2
fi

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SERVICE_ACCOUNT:-${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
SCHEDULER_SERVICE_ACCOUNT="${SCHEDULER_SERVICE_ACCOUNT:-${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
run_api="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com \
  bigquery.googleapis.com \
  drive.googleapis.com \
  iam.googleapis.com

ensure_service_account() {
  local account_id="$1"
  local display_name="$2"
  local email="${account_id}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "${email}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account_id}" --display-name "${display_name}" --project "${PROJECT_ID}"
  fi
}

ensure_project_role() {
  local principal="$1"
  local role="$2"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${principal}" \
    --role="${role}" \
    --condition=None >/dev/null
}

ensure_dataset() {
  local dataset="$1"
  if bq show --project_id="${PROJECT_ID}" "${PROJECT_ID}:${dataset}" >/dev/null 2>&1; then
    local actual_location
    actual_location="$(bq show --project_id="${PROJECT_ID}" --format=prettyjson "${PROJECT_ID}:${dataset}" | python -c 'import json,sys; print(json.load(sys.stdin).get("location", ""))')"
    if [[ -n "${actual_location}" && "${actual_location}" != "${BQ_LOCATION}" ]]; then
      echo "Dataset ${dataset} existe em ${actual_location}; esperado ${BQ_LOCATION}. Abortando." >&2
      exit 3
    fi
  else
    bq --location="${BQ_LOCATION}" mk --dataset "${PROJECT_ID}:${dataset}"
  fi
}

ensure_dataset_role() {
  local dataset="$1"
  local principal="$2"
  local role="$3"
  bq add-iam-policy-binding "${PROJECT_ID}:${dataset}" \
    --member="serviceAccount:${principal}" \
    --role="${role}" >/dev/null
}

ensure_service_account "${COLLECTOR_SA_NAME}" "AgroLog Collector"
ensure_service_account "${SCHEDULER_SA_NAME}" "AgroLog Scheduler Invoker"

# O coletor precisa criar/executar jobs BigQuery, mas escrita de dados fica limitada aos datasets AgroLog abaixo.
ensure_project_role "${COLLECTOR_SERVICE_ACCOUNT}" "roles/bigquery.user"
ensure_dataset "${OPS_DATASET}"
ensure_dataset "${LOGISTICA_DATASET}"
ensure_dataset_role "${OPS_DATASET}" "${COLLECTOR_SERVICE_ACCOUNT}" "roles/bigquery.dataEditor"
ensure_dataset_role "${LOGISTICA_DATASET}" "${COLLECTOR_SERVICE_ACCOUNT}" "roles/bigquery.dataEditor"

# O Scheduler apenas dispara os Cloud Run Jobs.
ensure_project_role "${SCHEDULER_SERVICE_ACCOUNT}" "roles/run.invoker"

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}" --project "${PROJECT_ID}"
fi

gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_LOGISTICA_DATASET=${LOGISTICA_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.pilot.json"

for group in radar dados conhecimento; do
  job="agrolog-${group}"
  gcloud run jobs deploy "${job}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
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
  if gcloud scheduler jobs describe "${scheduler}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${scheduler}" \
      --location "${REGION}" \
      --project "${PROJECT_ID}" \
      --schedule "${schedules[$group]}" \
      --time-zone "${TIME_ZONE}" \
      --uri "${uri}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  else
    gcloud scheduler jobs create http "${scheduler}" \
      --location "${REGION}" \
      --project "${PROJECT_ID}" \
      --schedule "${schedules[$group]}" \
      --time-zone "${TIME_ZONE}" \
      --uri "${uri}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  fi
done

cat <<EOF

Infraestrutura do coletor criada/atualizada.

Projeto: ${PROJECT_ID}
Região: ${REGION}
BigQuery: ${BQ_LOCATION}
Datasets de escrita: ${OPS_DATASET}, ${LOGISTICA_DATASET}
Pasta RAW/Drive: ${DRIVE_FOLDER_ID}
Collector SA: ${COLLECTOR_SERVICE_ACCOUNT}
Scheduler SA: ${SCHEDULER_SERVICE_ACCOUNT}

Gate externo do Drive:
A pasta RAW deve estar compartilhada como Editor com ${COLLECTOR_SERVICE_ACCOUNT}.

Homologação controlada:
gcloud run jobs execute agrolog-dados --region ${REGION} --project ${PROJECT_ID} --wait --update-env-vars "AGROLOG_SOURCE_ID=conab_armazens_cadastrados"
python scripts/validate_conab_n6.py --project ${PROJECT_ID}

Repita a execução CONAB e rode novamente validate_conab_n6.py para comprovar idempotência.
EOF
