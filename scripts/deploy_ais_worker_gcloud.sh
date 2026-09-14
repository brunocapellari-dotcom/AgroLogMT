#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
DATASET="${DATASET:-agrolog_models}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
IMAGE_NAME="${IMAGE_NAME:-collector}"
IMAGE_TAG="${IMAGE_TAG:-ais-$(date +%Y%m%d%H%M%S)}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
SECRET_NAME="${SECRET_NAME:-aisstream-api-key}"
AIS_JOB_NAME="${AIS_JOB_NAME:-agrolog-ais}"
RECON_JOB_NAME="${RECON_JOB_NAME:-agrolog-shipping-reconcile}"
CAPTURE_SECONDS="${AIS_CAPTURE_SECONDS:-3540}"
BATCH_SIZE="${AIS_BATCH_SIZE:-250}"
SHIPPING_LOOKBACK_DAYS="${SHIPPING_LOOKBACK_DAYS:-30}"
AIS_SUBSCRIPTION_CONFIG="${AIS_SUBSCRIPTION_CONFIG:-collector/config/maritime_ais_subscription.v1.json}"
AIS_BOUNDING_BOXES_JSON="${AIS_BOUNDING_BOXES_JSON:-}"
# Runtime geofences remain empty until GEOFENCE_VALIDATED.
AIS_PORT_ZONES_JSON="${AIS_PORT_ZONES_JSON:-[]}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
for cmd in gcloud bq python3; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SERVICE_ACCOUNT:-${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

gcloud config set project "$PROJECT_ID" >/dev/null

require_api() {
  local api="$1"
  gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api" || {
    echo "ERRO: API $api não habilitada. Execute o bootstrap administrativo." >&2
    exit 3
  }
}

for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com storage.googleapis.com secretmanager.googleapis.com; do
  require_api "$api"
done

for sa in "$COLLECTOR_SERVICE_ACCOUNT" "$BUILD_SERVICE_ACCOUNT"; do
  gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1 || {
    echo "ERRO: service account ausente: $sa. Execute scripts/setup_github_gcp_wif.sh com identidade administradora." >&2
    exit 3
  }
done

if ! bq show --project_id="$PROJECT_ID" "$PROJECT_ID:$DATASET" >/dev/null 2>&1; then
  echo "ERRO: dataset ${DATASET} ausente. Bootstrap administrativo obrigatório." >&2
  exit 3
fi
actual_location="$(bq show --project_id="$PROJECT_ID" --format=prettyjson "$PROJECT_ID:$DATASET" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("location", ""))')"
if [[ -n "$actual_location" && "$actual_location" != "$BQ_LOCATION" ]]; then
  echo "ERRO: dataset ${DATASET} em ${actual_location}; esperado ${BQ_LOCATION}" >&2
  exit 3
fi

gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: Artifact Registry ${AR_REPOSITORY} ausente. Bootstrap administrativo obrigatório." >&2
  exit 3
}
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: staging bucket ${BUILD_SOURCE_BUCKET} ausente. Bootstrap administrativo obrigatório." >&2
  exit 3
}

if [[ -z "$AIS_BOUNDING_BOXES_JSON" ]]; then
  [[ -f "$AIS_SUBSCRIPTION_CONFIG" ]] || { echo "ERRO: config AIS ausente: ${AIS_SUBSCRIPTION_CONFIG}" >&2; exit 2; }
  AIS_BOUNDING_BOXES_JSON="$(python3 - "$AIS_SUBSCRIPTION_CONFIG" <<'PY'
import json
import sys
from pathlib import Path
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
boxes = [area["bounding_box"] for area in payload["areas"]]
if len(boxes) != 5:
    raise SystemExit(f"expected 5 AIS pilot AOIs, got {len(boxes)}")
print(json.dumps(boxes, separators=(",", ":")))
PY
)"
fi

# Build uses the dedicated builder and staging bucket. This script never mutates IAM/APIs/datasets.
gcloud builds submit . \
  --project "$PROJECT_ID" \
  --service-account "$BUILD_SERVICE_ACCOUNT" \
  --gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source" \
  --config collector/cloudbuild.yaml \
  --substitutions "_IMAGE=${IMAGE}"

AIS_ENV="^@^AGROLOG_GCP_PROJECT=${PROJECT_ID}@AGROLOG_BQ_LOCATION=${BQ_LOCATION}@AIS_BOUNDING_BOXES_JSON=${AIS_BOUNDING_BOXES_JSON}@AIS_PORT_ZONES_JSON=${AIS_PORT_ZONES_JSON}@AIS_CAPTURE_SECONDS=${CAPTURE_SECONDS}@AIS_BATCH_SIZE=${BATCH_SIZE}"
gcloud run jobs deploy "$AIS_JOB_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$COLLECTOR_SERVICE_ACCOUNT" \
  --command python \
  --args=-m,collector.ais_worker \
  --set-env-vars "$AIS_ENV" \
  --set-secrets "AISSTREAM_API_KEY=${SECRET_NAME}:latest" \
  --max-retries 1 \
  --task-timeout 65m

RECON_ENV="AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_BQ_LOCATION=${BQ_LOCATION},SHIPPING_LOOKBACK_DAYS=${SHIPPING_LOOKBACK_DAYS}"
gcloud run jobs deploy "$RECON_JOB_NAME" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --service-account "$COLLECTOR_SERVICE_ACCOUNT" \
  --command python \
  --args=-m,collector.shipping_reconcile_worker \
  --set-env-vars "$RECON_ENV" \
  --max-retries 1 \
  --task-timeout 10m

cat <<EOF
AIS runtime atualizado sem mutação de IAM/APIs/datasets.
Projeto: ${PROJECT_ID}
Região: ${REGION}
Imagem: ${IMAGE}
Builder: ${BUILD_SERVICE_ACCOUNT}
Collector: ${COLLECTOR_SERVICE_ACCOUNT}
AIS job: ${AIS_JOB_NAME} (${CAPTURE_SECONDS}s por execução)
Reconciliation job: ${RECON_JOB_NAME}
Dataset: ${PROJECT_ID}.${DATASET}
AOIs: ${AIS_BOUNDING_BOXES_JSON}
Geofences operacionais: ${AIS_PORT_ZONES_JSON}

O agendamento é externo ao deploy. Durante o fechamento da Maritime V1, GitHub Actions dispara ${AIS_JOB_NAME} a cada hora.
EOF
