#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
DATASET="${DATASET:-agrolog_models}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-ais-$(date +%Y%m%d%H%M%S)}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
SCHEDULER_SA_NAME="${SCHEDULER_SA_NAME:-agrolog-scheduler}"
SECRET_NAME="${SECRET_NAME:-aisstream-api-key}"
JOB_NAME="${JOB_NAME:-agrolog-ais}"
SCHEDULER_NAME="${SCHEDULER_NAME:-agrolog-ais-hourly}"
TIME_ZONE="${TIME_ZONE:-America/Cuiaba}"
CAPTURE_SECONDS="${AIS_CAPTURE_SECONDS:-3000}"
BATCH_SIZE="${AIS_BATCH_SIZE:-250}"
# Broad pilot subscription around Santos. This is not a berth/anchorage geofence.
AIS_BOUNDING_BOXES_JSON="${AIS_BOUNDING_BOXES_JSON:-[[[-25.0,-47.0],[-23.0,-45.0]]]}"
AIS_PORT_ZONES_JSON="${AIS_PORT_ZONES_JSON:-[]}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
command -v gcloud >/dev/null || { echo 'ERRO: gcloud ausente' >&2; exit 2; }
command -v bq >/dev/null || { echo 'ERRO: bq ausente' >&2; exit 2; }

gcloud config set project "$PROJECT_ID" >/dev/null

gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  bigquery.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com iam.googleapis.com \
  --project "$PROJECT_ID" >/dev/null

COLLECTOR_SA="${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
for spec in "${COLLECTOR_SA_NAME}:AgroLog Collector" "${SCHEDULER_SA_NAME}:AgroLog Scheduler"; do
  name="${spec%%:*}"; display="${spec#*:}"
  email="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$email" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --display-name "$display" --project "$PROJECT_ID" >/dev/null
  fi
done

if ! gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "ERRO: segredo ${SECRET_NAME} ausente. Execute scripts/setup_aisstream_secret.sh primeiro." >&2
  exit 3
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${COLLECTOR_SA}" --role="roles/bigquery.user" --condition=None >/dev/null

gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --project "$PROJECT_ID" --member="serviceAccount:${COLLECTOR_SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SCHEDULER_SA}" --role="roles/run.invoker" --condition=None >/dev/null

if bq show --project_id="$PROJECT_ID" "$PROJECT_ID:$DATASET" >/dev/null 2>&1; then
  actual_location="$(bq show --project_id="$PROJECT_ID" --format=prettyjson "$PROJECT_ID:$DATASET" | python -c 'import json,sys; print(json.load(sys.stdin).get("location", ""))')"
  if [[ -n "$actual_location" && "$actual_location" != "$BQ_LOCATION" ]]; then
    echo "ERRO: dataset ${DATASET} em ${actual_location}; esperado ${BQ_LOCATION}" >&2
    exit 4
  fi
else
  bq --location="$BQ_LOCATION" mk --dataset "$PROJECT_ID:$DATASET"
fi

bq query --project_id="$PROJECT_ID" --location="$BQ_LOCATION" --use_legacy_sql=false --quiet \
  "GRANT \`roles/bigquery.dataEditor\` ON SCHEMA \`${PROJECT_ID}\`.${DATASET} TO \"serviceAccount:${COLLECTOR_SA}\""

if ! gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPOSITORY" --repository-format=docker --location "$REGION" --project "$PROJECT_ID" >/dev/null
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"
gcloud builds submit --tag "$IMAGE" --project "$PROJECT_ID" .

ENV_SPEC="^@^AGROLOG_GCP_PROJECT=${PROJECT_ID}@AGROLOG_BQ_LOCATION=${BQ_LOCATION}@AIS_BOUNDING_BOXES_JSON=${AIS_BOUNDING_BOXES_JSON}@AIS_PORT_ZONES_JSON=${AIS_PORT_ZONES_JSON}@AIS_CAPTURE_SECONDS=${CAPTURE_SECONDS}@AIS_BATCH_SIZE=${BATCH_SIZE}"

gcloud run jobs deploy "$JOB_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$COLLECTOR_SA" \
  --command python \
  --args=-m,collector.ais_worker \
  --set-env-vars "$ENV_SPEC" \
  --set-secrets "AISSTREAM_API_KEY=${SECRET_NAME}:latest" \
  --max-retries 1 \
  --task-timeout 55m

RUN_URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${JOB_NAME}:run"
if gcloud scheduler jobs describe "$SCHEDULER_NAME" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_NAME" \
    --location "$REGION" --project "$PROJECT_ID" \
    --schedule "5 * * * *" --time-zone "$TIME_ZONE" \
    --uri "$RUN_URI" --http-method POST \
    --oauth-service-account-email "$SCHEDULER_SA" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
else
  gcloud scheduler jobs create http "$SCHEDULER_NAME" \
    --location "$REGION" --project "$PROJECT_ID" \
    --schedule "5 * * * *" --time-zone "$TIME_ZONE" \
    --uri "$RUN_URI" --http-method POST \
    --oauth-service-account-email "$SCHEDULER_SA" \
    --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
fi

cat <<EOF
OK: AIS worker implantado.
Job: ${JOB_NAME}
Captura por execução: ${CAPTURE_SECONDS}s
Agendamento: minuto 05 de cada hora (${TIME_ZONE})
Dataset: ${PROJECT_ID}.${DATASET}
Piloto bounding box: ${AIS_BOUNDING_BOXES_JSON}

Teste manual:
gcloud run jobs execute ${JOB_NAME} --region ${REGION} --project ${PROJECT_ID} --wait --update-env-vars AIS_MAX_RECORDS=10,AIS_CAPTURE_SECONDS=120
EOF
