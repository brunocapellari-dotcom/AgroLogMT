#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
PECUARIA_DATASET="${PECUARIA_DATASET:-pecuaria}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: configure PROJECT_ID/gcloud project" >&2
  exit 2
fi
for cmd in gcloud bq; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done

gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || {
  echo "ERRO: bootstrap exige identidade humana administradora autenticada no gcloud" >&2
  exit 2
}

COLLECTOR_SA="${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GATEWAY_SA="${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

for sa in "$COLLECTOR_SA" "$GATEWAY_SA"; do
  gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null
done

if bq show --project_id="$PROJECT_ID" "${PROJECT_ID}:${PECUARIA_DATASET}" >/dev/null 2>&1; then
  actual="$(bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${PECUARIA_DATASET}" | python -c 'import json,sys; print(json.load(sys.stdin).get("location", ""))')"
  if [[ -n "$actual" && "$actual" != "$BQ_LOCATION" ]]; then
    echo "ERRO: dataset ${PECUARIA_DATASET} existe em ${actual}; esperado ${BQ_LOCATION}" >&2
    exit 3
  fi
else
  bq --location="$BQ_LOCATION" mk --dataset "${PROJECT_ID}:${PECUARIA_DATASET}"
fi

bq show --project_id="$PROJECT_ID" "${PROJECT_ID}:${TRADE_DATASET}" >/dev/null 2>&1 || {
  echo "ERRO: dataset ${TRADE_DATASET} ausente; execute o bootstrap principal do AgroLog primeiro" >&2
  exit 3
}

bq query --project_id="$PROJECT_ID" --location="$BQ_LOCATION" --use_legacy_sql=false --quiet \
  "GRANT \`roles/bigquery.dataEditor\` ON SCHEMA \`${PROJECT_ID}\`.${PECUARIA_DATASET} TO \"serviceAccount:${COLLECTOR_SA}\""

bq query --project_id="$PROJECT_ID" --location="$BQ_LOCATION" --use_legacy_sql=false --quiet \
  "GRANT \`roles/bigquery.dataViewer\` ON SCHEMA \`${PROJECT_ID}\`.${PECUARIA_DATASET} TO \"serviceAccount:${GATEWAY_SA}\""

bq query --project_id="$PROJECT_ID" --location="$BQ_LOCATION" --use_legacy_sql=false --quiet \
  "GRANT \`roles/bigquery.dataViewer\` ON SCHEMA \`${PROJECT_ID}\`.${TRADE_DATASET} TO \"serviceAccount:${GATEWAY_SA}\""

echo "PECUARIA_BOOTSTRAP_PASS project=${PROJECT_ID} dataset=${PECUARIA_DATASET} location=${BQ_LOCATION}"
echo "Collector editor: ${COLLECTOR_SA} -> ${PECUARIA_DATASET}"
echo "Gateway viewer:  ${GATEWAY_SA} -> ${PECUARIA_DATASET}, ${TRADE_DATASET}"
