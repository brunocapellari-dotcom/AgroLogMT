#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
DRIVE_FOLDER_ID="${DRIVE_FOLDER_ID:-17AX2iCrQ17Jm86Pp9ijqn3hyEHVaQPqd}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
TIME_ZONE="${TIME_ZONE:-America/Campo_Grande}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"
ANA_IDENTIFIER_SECRET="${ANA_IDENTIFIER_SECRET:-agrolog-ana-identificador}"
ANA_PASSWORD_SECRET="${ANA_PASSWORD_SECRET:-agrolog-ana-senha}"
DATA_GOV_API_KEY_SECRET="${DATA_GOV_API_KEY_SECRET:-agrolog-api-data-gov-key}"

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
  iam.googleapis.com \
  secretmanager.googleapis.com

ensure_service_account() {
  local account_id="$1"
  local display_name="$2"
  local email="${account_id}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "${email}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account_id}" --display-name "${display_name}"
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

ensure_secret() {
  local secret_name="$1"
  if ! gcloud secrets describe "${secret_name}" >/dev/null 2>&1; then
    gcloud secrets create "${secret_name}" --replication-policy=automatic >/dev/null
  fi
}

secret_has_enabled_version() {
  local secret_name="$1"
  [[ -n "$(gcloud secrets versions list "${secret_name}" --filter='state=ENABLED' --format='value(name)' --limit=1 2>/dev/null)" ]]
}

add_secret_version_if_missing() {
  local secret_name="$1"
  local env_name="$2"
  local prompt_label="$3"
  local secret_mode="$4"

  ensure_secret "${secret_name}"
  if secret_has_enabled_version "${secret_name}"; then
    return 0
  fi

  local value="${!env_name:-}"
  if [[ -z "${value}" ]]; then
    if [[ ! -t 0 ]]; then
      echo "Secret ${secret_name} ainda nao possui versao. Execute o deploy em terminal interativo ou defina ${env_name} somente durante o deploy." >&2
      exit 2
    fi
    if [[ "${secret_mode}" == "hidden" ]]; then
      read -r -s -p "${prompt_label}: " value
      echo
    else
      read -r -p "${prompt_label}: " value
    fi
  fi

  if [[ -z "${value}" ]]; then
    echo "Valor vazio para ${secret_name}; deploy interrompido." >&2
    exit 2
  fi

  printf '%s' "${value}" | gcloud secrets versions add "${secret_name}" --data-file=- >/dev/null
  unset value
}

bind_secret_access() {
  local secret_name="$1"
  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --member="serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None >/dev/null
}

ensure_service_account "${COLLECTOR_SA_NAME}" "AgroLog Collector"
ensure_service_account "${SCHEDULER_SA_NAME}" "AgroLog Scheduler Invoker"

# BigQuery User permite executar jobs e criar o dataset operacional do coletor.
# Ao criar o dataset, a identidade criadora recebe ownership sobre ele.
ensure_project_role "${COLLECTOR_SERVICE_ACCOUNT}" "roles/bigquery.user"

# O Scheduler precisa apenas iniciar os Cloud Run Jobs.
ensure_project_role "${SCHEDULER_SERVICE_ACCOUNT}" "roles/run.invoker"

# Credenciais e chaves externas ficam somente no Secret Manager e sao injetadas no job de Dados.
add_secret_version_if_missing "${ANA_IDENTIFIER_SECRET}" "ANA_IDENTIFICADOR" "Identificador da API ANA" "hidden"
add_secret_version_if_missing "${ANA_PASSWORD_SECRET}" "ANA_SENHA" "Senha da API ANA" "hidden"
add_secret_version_if_missing "${DATA_GOV_API_KEY_SECRET}" "DATA_GOV_API_KEY" "Chave api.data.gov / USDA FAS" "hidden"
bind_secret_access "${ANA_IDENTIFIER_SECRET}"
bind_secret_access "${ANA_PASSWORD_SECRET}"
bind_secret_access "${DATA_GOV_API_KEY_SECRET}"

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}"
fi

gcloud builds submit --tag "${IMAGE}" .

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.pilot.json"

for group in radar dados conhecimento; do
  job="agrolog-${group}"
  extra_args=()
  if [[ "${group}" == "dados" ]]; then
    extra_args+=(--set-secrets "ANA_IDENTIFICADOR=${ANA_IDENTIFIER_SECRET}:latest,ANA_SENHA=${ANA_PASSWORD_SECRET}:latest,DATA_GOV_API_KEY=${DATA_GOV_API_KEY_SECRET}:latest")
  fi
  gcloud run jobs deploy "${job}" \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --service-account "${COLLECTOR_SERVICE_ACCOUNT}" \
    --set-env-vars "${common_env},AGROLOG_GROUP=${group}" \
    "${extra_args[@]}" \
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

cat <<EOF

Infraestrutura criada/atualizada.

Projeto: ${PROJECT_ID}
Regiao: ${REGION}
Pasta Drive do piloto: ${DRIVE_FOLDER_ID}
Collector SA: ${COLLECTOR_SERVICE_ACCOUNT}
Scheduler SA: ${SCHEDULER_SERVICE_ACCOUNT}
ANA secrets: ${ANA_IDENTIFIER_SECRET}, ${ANA_PASSWORD_SECRET}
api.data.gov secret: ${DATA_GOV_API_KEY_SECRET}

PASSO MANUAL UNICO DO DRIVE:
Compartilhe a pasta 07_AUTOMACAO como Editor com:
${COLLECTOR_SERVICE_ACCOUNT}

Depois teste:
gcloud run jobs execute agrolog-dados --region ${REGION} --wait

Se o teste terminar com sucesso, verifique:
- Drive: 07_AUTOMACAO/RAW/dados/ana_hidroweb_*/...
- Drive: 07_AUTOMACAO/RAW/dados/usda_fas_*/...
- BigQuery: ${OPS_DATASET}.collector_runs
- BigQuery: ${OPS_DATASET}.collector_source_state
EOF