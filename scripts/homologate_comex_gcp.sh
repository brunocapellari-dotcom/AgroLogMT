#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
JOB="${JOB:-agrolog-dados}"
SOURCE_ID="mdic_comexstat_soja_mt_export_api"
CONFIG="/app/collector/config/sources.p0.json"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Defina PROJECT_ID ou configure gcloud project." >&2
  exit 2
fi

run_once() {
  gcloud run jobs execute "${JOB}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --wait \
    --update-env-vars "AGROLOG_CONFIG=${CONFIG},AGROLOG_SOURCE_ID=${SOURCE_ID},AGROLOG_TRADE_DATASET=${TRADE_DATASET}"
}

validate_once() {
  local extra=("$@")
  python scripts/validate_comexstat_bigquery.py \
    --project "${PROJECT_ID}" \
    --dataset "${TRADE_DATASET}" \
    --ops-dataset "${OPS_DATASET}" \
    --location "${BQ_LOCATION}" \
    "${extra[@]}"
}

echo "[1/4] Primeira execução ComexStat"
run_once

echo "[2/4] Validação da materialização inicial"
validate_once

echo "[3/4] Segunda execução da mesma competência"
run_once

echo "[4/4] Validação com gate de idempotência"
validate_once --require-idempotency

echo "COMEXSTAT_HOMOLOGATION_PASS project=${PROJECT_ID} dataset=${TRADE_DATASET}"
