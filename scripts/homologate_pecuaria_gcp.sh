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
SLAUGHTER_SOURCE_ID="ibge_sidra_slaughter_1092"
SIGSIF_SOURCE_ID="mapa_sigsif_slaughter_snapshot"
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

validate_domain() {
  local scope="$1"
  shift
  python scripts/validate_pecuaria_bigquery.py \
    --project "${PROJECT_ID}" \
    --dataset "${PECUARIA_DATASET}" \
    --ops-dataset "${OPS_DATASET}" \
    --location "${BQ_LOCATION}" \
    --scope "${scope}" \
    "$@"
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

echo "[1/16] PPM primeira execução"
run_source "${PPM_SOURCE_ID}"
echo "[2/16] PPM validação inicial"
validate_domain ppm
echo "[3/16] PPM segunda execução"
run_source "${PPM_SOURCE_ID}"
echo "[4/16] PPM gate de idempotência"
validate_domain ppm --require-idempotency

echo "[5/16] IBGE Abate primeira execução"
run_source "${SLAUGHTER_SOURCE_ID}"
echo "[6/16] IBGE Abate validação inicial"
validate_domain slaughter
echo "[7/16] IBGE Abate segunda execução"
run_source "${SLAUGHTER_SOURCE_ID}"
echo "[8/16] IBGE Abate gate de idempotência"
validate_domain slaughter --require-idempotency

echo "[9/16] SIGSIF primeira execução"
run_source "${SIGSIF_SOURCE_ID}"
echo "[10/16] SIGSIF validação inicial"
validate_domain sigsif
echo "[11/16] SIGSIF segunda execução"
run_source "${SIGSIF_SOURCE_ID}"
echo "[12/16] SIGSIF gate de idempotência"
validate_domain sigsif --require-idempotency

echo "[13/16] Comex bovino primeira execução"
run_source "${BEEF_SOURCE_ID}"
echo "[14/16] Comex bovino validação inicial"
validate_beef
echo "[15/16] Comex bovino segunda execução"
run_source "${BEEF_SOURCE_ID}"
echo "[16/16] Comex bovino gate de idempotência"
validate_beef --require-idempotency

# Final aggregate gate proves the three domestic livestock tables together.
validate_domain all --require-idempotency

restore_group_mode
trap - EXIT

echo "PECUARIA_HOMOLOGATION_PASS project=${PROJECT_ID} ppm_dataset=${PECUARIA_DATASET} trade_dataset=${TRADE_DATASET} feeds=4"
