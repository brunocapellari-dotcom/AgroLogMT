#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
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

log_step "7. Gate ComexStat API -> Drive/BigQuery + idempotência"
PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" \
  bash scripts/homologate_comex_gcp.sh \
  2>&1 | tee "${RUN_DIR}/07-comex-homologation.log"
grep -Fq 'COMEXSTAT_HOMOLOGATION_PASS' "${RUN_DIR}/07-comex-homologation.log"

log_step "8. Deploy Gateway"
bash scripts/deploy_gateway_gcloud.sh 2>&1 | tee "${RUN_DIR}/08-deploy-gateway.log"

log_step "9. Deploy Freight Ingest"
bash scripts/deploy_freight_ingest_gcloud.sh 2>&1 | tee "${RUN_DIR}/09-deploy-freight-ingest.log"
grep -Fq 'FREIGHT_INGEST_DEPLOY_PASS' "${RUN_DIR}/09-deploy-freight-ingest.log"

log_step "10. Validação Gateway x BigQuery"
python scripts/validate_gateway_n6.py \
  --project "${PROJECT_ID}" --region "${REGION}" \
  --out "${RUN_DIR}/10-gateway-validation.json" \
  2>&1 | tee "${RUN_DIR}/10-gateway-validation.log"

cat > "${RUN_DIR}/RESULT.txt" <<EOF
N6 CORE HOMOLOGATION: PASS
project=${PROJECT_ID}
region=${REGION}
conab_source=${CONAB_SOURCE_ID}
comex_source=${COMEX_SOURCE_ID}
comex_gate=PASS
freight_ingest_gate=PASS
generated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
evidence_dir=${RUN_DIR}
EOF

cat "${RUN_DIR}/RESULT.txt"
