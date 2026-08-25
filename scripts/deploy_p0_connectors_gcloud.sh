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
PTAX_JOB="agrolog-ptax"
ANA_JOB="agrolog-ana-hidro"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  cloudscheduler.googleapis.com bigquery.googleapis.com drive.googleapis.com iam.googleapis.com secretmanager.googleapis.com

for account in "${COLLECTOR_SA_NAME}" "${SCHEDULER_SA_NAME}"; do
  email="${account}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "${email}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account}" --project "${PROJECT_ID}" --display-name "${account}"
  fi
done

gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}" --role="roles/bigquery.user" --condition=None >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SCHEDULER_SERVICE_ACCOUNT}" --role="roles/run.invoker" --condition=None >/dev/null

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

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPOSITORY}" --repository-format=docker --location "${REGION}" --project "${PROJECT_ID}"
fi
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

common_env="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_OPS_DATASET=${OPS_DATASET},AGROLOG_MERCADO_DATASET=${MERCADO_DATASET},AGROLOG_HIDRO_DATASET=${HIDRO_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_DRIVE_FOLDER_ID=${DRIVE_FOLDER_ID},AGROLOG_CONFIG=/app/collector/config/sources.p0.json"

# PTAX é independente e nunca deve ficar bloqueada pela configuração dos secrets ANA.
gcloud run jobs deploy "${PTAX_JOB}" --image "${IMAGE}" --region "${REGION}" --project "${PROJECT_ID}" \
  --service-account "${COLLECTOR_SERVICE_ACCOUNT}" \
  --set-env-vars "${common_env},AGROLOG_GROUP=dados,AGROLOG_SOURCE_ID=bcb_ptax_usd_daily" \
  --max-retries 1 --task-timeout 10m

schedule_job() {
  local scheduler="$1" job="$2" schedule="$3"
  local uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${job}:run"
  if gcloud scheduler jobs describe "${scheduler}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${scheduler}" --location "${REGION}" --project "${PROJECT_ID}" \
      --schedule "${schedule}" --time-zone "${TIME_ZONE}" --uri "${uri}" --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  else
    gcloud scheduler jobs create http "${scheduler}" --location "${REGION}" --project "${PROJECT_ID}" \
      --schedule "${schedule}" --time-zone "${TIME_ZONE}" --uri "${uri}" --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SERVICE_ACCOUNT}" --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  fi
}
# Janela de publicação/checagem; o coletor sempre seleciona a última observação oficial retornada.
schedule_job "agrolog-ptax-weekday" "${PTAX_JOB}" "0 12-17 * * 1-5"

ANA_READY=true
for secret in "${ANA_IDENTIFICADOR_SECRET}" "${ANA_SENHA_SECRET}"; do
  if ! gcloud secrets describe "${secret}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    ANA_READY=false
  fi
done

if [[ "${ANA_READY}" == "true" ]]; then
  for secret in "${ANA_IDENTIFICADOR_SECRET}" "${ANA_SENHA_SECRET}"; do
    gcloud secrets add-iam-policy-binding "${secret}" --project "${PROJECT_ID}" \
      --member="serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}" --role="roles/secretmanager.secretAccessor" >/dev/null
  done
  gcloud run jobs deploy "${ANA_JOB}" --image "${IMAGE}" --region "${REGION}" --project "${PROJECT_ID}" \
    --service-account "${COLLECTOR_SERVICE_ACCOUNT}" \
    --set-env-vars "${common_env},AGROLOG_GROUP=dados,AGROLOG_SOURCE_ID=ana_hidroweb_m04_stations" \
    --set-secrets "ANA_IDENTIFICADOR=${ANA_IDENTIFICADOR_SECRET}:latest,ANA_SENHA=${ANA_SENHA_SECRET}:latest" \
    --max-retries 1 --task-timeout 30m
  schedule_job "agrolog-ana-hidro-hourly" "${ANA_JOB}" "0 * * * *"
else
  echo "ANA_NOT_DEPLOYED: crie os secrets ${ANA_IDENTIFICADOR_SECRET} e ${ANA_SENHA_SECRET} no Secret Manager; PTAX foi implantada normalmente." >&2
fi

cat <<EOF
P0 deploy concluído até o gate disponível.
image=${IMAGE}
ptax_job=${PTAX_JOB}
ana_job=$([[ "${ANA_READY}" == "true" ]] && echo "${ANA_JOB}" || echo "NOT_DEPLOYED_SECRETS_MISSING")
ptax_table=${PROJECT_ID}.${MERCADO_DATASET}.ptax_usd_daily
hydro_table=${PROJECT_ID}.${HIDRO_DATASET}.hydro_station_telemetry

Homologação PTAX:
gcloud run jobs execute ${PTAX_JOB} --region ${REGION} --project ${PROJECT_ID} --wait
python scripts/backfill_ptax_2026.py
python scripts/build_market_freshness_views.py

Homologação ANA (quando secrets existirem):
gcloud run jobs execute ${ANA_JOB} --region ${REGION} --project ${PROJECT_ID} --wait
python scripts/backfill_m04_ana.py --start 2023-01-01
python scripts/build_m04_hydro_views.py
EOF
