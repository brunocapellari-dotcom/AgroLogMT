#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
PECUARIA_DATASET="${PECUARIA_DATASET:-pecuaria}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
JOB="${JOB:-agrolog-pecuaria}"
PPM_SOURCE_ID="ibge_sidra_ppm_3939"
BEEF_SOURCE_ID="mdic_comexstat_beef_mt_export_api"
CONFIG="/app/collector/config/sources.pecuaria.json"
BEEF_NCMS=(02011000 02012010 02012020 02012090 02013000 02021000 02022010 02022020 02022090 02023000)

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Defina PROJECT_ID ou configure gcloud project." >&2
  exit 2
fi

restore_group_mode() {
  gcloud run jobs update "${JOB}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --remove-env-vars "AGROLOG_SOURCE_ID" \
    --update-env-vars "AGROLOG_CONFIG=${CONFIG},AGROLOG_GROUP=pecuaria,AGROLOG_PECUARIA_DATASET=${PECUARIA_DATASET},AGROLOG_TRADE_DATASET=${TRADE_DATASET}" \
    --quiet >/dev/null || true
}
trap restore_group_mode EXIT

run_source() {
  local source_id="$1"
  gcloud run jobs execute "${JOB}" \
    --region "${REGION}" \
    --project "${PROJECT_ID}" \
    --wait \
    --update-env-vars "AGROLOG_CONFIG=${CONFIG},AGROLOG_SOURCE_ID=${source_id},AGROLOG_PECUARIA_DATASET=${PECUARIA_DATASET},AGROLOG_TRADE_DATASET=${TRADE_DATASET}"
}

validate_ppm() {
  local extra=("$@")
  python scripts/validate_pecuaria_bigquery.py \
    --project "${PROJECT_ID}" \
    --dataset "${PECUARIA_DATASET}" \
    --ops-dataset "${OPS_DATASET}" \
    --location "${BQ_LOCATION}" \
    "${extra[@]}"
}

validate_beef() {
  local extra=("$@")
  local args=(
    --project "${PROJECT_ID}"
    --dataset "${TRADE_DATASET}"
    --ops-dataset "${OPS_DATASET}"
    --location "${BQ_LOCATION}"
    --source-id "${BEEF_SOURCE_ID}"
    --state "Mato Grosso"
    --flow export
  )
  local ncm
  for ncm in "${BEEF_NCMS[@]}"; do
    args+=(--ncm "$ncm")
  done
  python scripts/validate_comexstat_bigquery.py "${args[@]}" "${extra[@]}"
}

echo "[1/8] PPM primeira execução"
run_source "${PPM_SOURCE_ID}"
echo "[2/8] PPM validação inicial"
validate_ppm
echo "[3/8] PPM segunda execução"
run_source "${PPM_SOURCE_ID}"
echo "[4/8] PPM gate de idempotência"
validate_ppm --require-idempotency

echo "[5/8] Comex bovino primeira execução"
run_source "${BEEF_SOURCE_ID}"
echo "[6/8] Comex bovino validação inicial"
validate_beef
echo "[7/8] Comex bovino segunda execução"
run_source "${BEEF_SOURCE_ID}"
echo "[8/8] Comex bovino gate de idempotência"
validate_beef --require-idempotency

restore_group_mode
trap - EXIT

echo "PECUARIA_HOMOLOGATION_PASS project=${PROJECT_ID} ppm_dataset=${PECUARIA_DATASET} trade_dataset=${TRADE_DATASET}"
