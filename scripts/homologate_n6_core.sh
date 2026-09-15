#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
EVIDENCE_DIR="${EVIDENCE_DIR:-outputs/n6-core}"
CONAB_SOURCE_ID="conab_armazens_cadastrados"
COMEX_SOURCE_ID="mdic_comexstat_soja_mt_export_api"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Projeto GCP ausente" >&2
  exit 2
fi

mkdir -p "${EVIDENCE_DIR}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${EVIDENCE_DIR}/${TS}"
mkdir -p "${RUN_DIR}"

log_step() {
  printf '\n===== %s =====\n' "$1" | tee -a "${RUN_DIR}/homologation.log"
}

log_step "1. Preflight read-only"
bash scripts/preflight_n6_gcp.sh 2>&1 | tee "${RUN_DIR}/01-preflight.log"

log_step "2. Deploy/redeploy collector"
bash scripts/deploy_collectors_gcloud.sh 2>&1 | tee "${RUN_DIR}/02-deploy-collector.log"

log_step "3. Primeira execução CONAB"
gcloud run jobs execute agrolog-dados \
  --region "${REGION}" --project "${PROJECT_ID}" --wait \
  --update-env-vars "AGROLOG_SOURCE_ID=${CONAB_SOURCE_ID}" \
  2>&1 | tee "${RUN_DIR}/03-conab-first.log"

log_step "4. Validação após primeira carga CONAB"
python scripts/validate_conab_n6.py \
  --project "${PROJECT_ID}" \
  --out "${RUN_DIR}/04-conab-first-validation.json" \
  2>&1 | tee "${RUN_DIR}/04-conab-first-validation.log" || true

log_step "5. Segunda execução CONAB para idempotência"
gcloud run jobs execute agrolog-dados \
  --region "${REGION}" --project "${PROJECT_ID}" --wait \
  --update-env-vars "AGROLOG_SOURCE_ID=${CONAB_SOURCE_ID}" \
  2>&1 | tee "${RUN_DIR}/05-conab-second.log"

log_step "6. Gate final CONAB"
python scripts/validate_conab_n6.py \
  --project "${PROJECT_ID}" \
  --out "${RUN_DIR}/06-conab-final-validation.json" \
  2>&1 | tee "${RUN_DIR}/06-conab-final-validation.log"

log_step "7. Gate ComexStat soja API -> Drive/BigQuery + idempotência"
PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" \
  bash scripts/homologate_comex_gcp.sh \
  2>&1 | tee "${RUN_DIR}/07-comex-homologation.log"
grep -Fq 'COMEXSTAT_HOMOLOGATION_PASS' "${RUN_DIR}/07-comex-homologation.log"

log_step "8. Gate Pecuária: quatro feeds gated + BigQuery + idempotência"
PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" BQ_LOCATION="${BQ_LOCATION}" \
  bash scripts/homologate_pecuaria_gcp.sh \
  2>&1 | tee "${RUN_DIR}/08-pecuaria-homologation.log"
grep -Fq 'PECUARIA_HOMOLOGATION_PASS' "${RUN_DIR}/08-pecuaria-homologation.log"

log_step "9. View histórica de exportação bovina + validação temporal"
python scripts/deploy_pecuaria_views.py \
  --project "${PROJECT_ID}" \
  --trade-dataset "${TRADE_DATASET}" \
  --location "${BQ_LOCATION}" \
  2>&1 | tee "${RUN_DIR}/09-pecuaria-trade-view.log"
python scripts/validate_pecuaria_trade_history.py \
  --project "${PROJECT_ID}" \
  --dataset "${TRADE_DATASET}" \
  --location "${BQ_LOCATION}" \
  2>&1 | tee "${RUN_DIR}/09-pecuaria-trade-validation.log"

log_step "10. Deploy único do Gateway endurecido"
bash scripts/deploy_gateway_gcloud.sh 2>&1 | tee "${RUN_DIR}/10-deploy-gateway.log"

log_step "11. Validação Gateway core x BigQuery"
python scripts/validate_gateway_n6.py \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --out "${RUN_DIR}/11-gateway-validation.json" \
  2>&1 | tee "${RUN_DIR}/11-gateway-validation.log"

log_step "12. Validação Gateway Pecuária end-to-end"
python scripts/validate_pecuaria_gateway.py \
  --project "${PROJECT_ID}" --region "${REGION}" \
  2>&1 | tee "${RUN_DIR}/12-pecuaria-gateway-validation.log"

cat > "${RUN_DIR}/RESULT.txt" <<EOF
N6 CORE HOMOLOGATION: PASS
project=${PROJECT_ID}
region=${REGION}
conab_source=${CONAB_SOURCE_ID}
comex_source=${COMEX_SOURCE_ID}
comex_gate=PASS
pecuaria_feeds_gate=PASS
pecuaria_trade_history_gate=PASS
pecuaria_gateway_gate=PASS
pecuaria_registry_promotion=NOT_AUTOMATIC
generated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
evidence_dir=${RUN_DIR}
EOF

cat "${RUN_DIR}/RESULT.txt"
