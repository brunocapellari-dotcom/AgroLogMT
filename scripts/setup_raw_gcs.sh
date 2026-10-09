#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
RAW_BUCKET="${RAW_BUCKET:-${PROJECT_ID}-agrolog-raw}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi

COLLECTOR_SERVICE_ACCOUNT="${COLLECTOR_SERVICE_ACCOUNT:-${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable storage.googleapis.com --project "$PROJECT_ID" >/dev/null

if ! gcloud storage buckets describe "gs://${RAW_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${RAW_BUCKET}"     --project "$PROJECT_ID"     --location "$REGION"     --uniform-bucket-level-access
fi

gcloud storage buckets update "gs://${RAW_BUCKET}"   --project "$PROJECT_ID"   --public-access-prevention   --uniform-bucket-level-access

for role in roles/storage.objectCreator roles/storage.objectViewer; do
  gcloud storage buckets add-iam-policy-binding "gs://${RAW_BUCKET}"     --project "$PROJECT_ID"     --member "serviceAccount:${COLLECTOR_SERVICE_ACCOUNT}"     --role "$role" >/dev/null
done

gcloud storage buckets describe "gs://${RAW_BUCKET}" --project "$PROJECT_ID"   --format="yaml(name,location,uniformBucketLevelAccess,publicAccessPrevention)"

echo "RAW_GCS_READY"
echo "bucket=gs://${RAW_BUCKET}"
echo "collector=${COLLECTOR_SERVICE_ACCOUNT}"
