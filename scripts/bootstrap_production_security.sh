#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
REQUIRED_CHECK="${REQUIRED_CHECK:-Whole project deterministic gate}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo 'ERRO: configure o projeto GCP correto antes do bootstrap.' >&2
  exit 2
fi
for cmd in gh gcloud bq python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERRO: ${cmd} ausente" >&2; exit 2; }
done
gh auth status >/dev/null 2>&1 || { echo 'ERRO: gh não autenticado.' >&2; exit 2; }
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || {
  echo 'ERRO: nenhuma identidade gcloud ativa.' >&2
  exit 2
}

printf '== 1/5 GitHub repository hardening ==\n'
REPO="$REPO" REQUIRED_CHECK="$REQUIRED_CHECK" bash scripts/harden_github_repository.sh

printf '== 2/5 GCP/WIF bootstrap ==\n'
REPO="$REPO" PROJECT_ID="$PROJECT_ID" BUILD_SOURCE_BUCKET="$BUILD_SOURCE_BUCKET" \
  bash scripts/setup_github_gcp_wif.sh

printf '== 3/5 Storage public-access prevention ==\n'
gcloud storage buckets update "gs://${BUILD_SOURCE_BUCKET}" --public-access-prevention=enforced >/dev/null
actual_pap="$(gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --format='value(iamConfiguration.publicAccessPrevention)' 2>/dev/null || true)"
if [[ "$actual_pap" != "enforced" ]]; then
  echo "ERRO: Public Access Prevention não está enforced no staging bucket." >&2
  exit 4
fi
printf 'OK Public Access Prevention=enforced\n'

printf '== 4/5 Long-lived service-account key audit ==\n'
for name in agrolog-github-deployer agrolog-builder agrolog-collector agrolog-gateway agrolog-freight-ingest; do
  sa="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  keys="$(gcloud iam service-accounts keys list \
    --iam-account="$sa" --managed-by=user --project="$PROJECT_ID" --format='value(name)' 2>/dev/null || true)"
  if [[ -n "$keys" ]]; then
    echo "ERRO: chave USER_MANAGED proibida em ${sa}. Revogue-a antes de prosseguir." >&2
    exit 4
  fi
  printf 'OK sem USER_MANAGED key: %s\n' "$sa"
done

printf '== 5/5 Production preflight ==\n'
PROJECT_ID="$PROJECT_ID" REGION="$REGION" BUILD_SOURCE_BUCKET="$BUILD_SOURCE_BUCKET" \
  bash scripts/preflight_n6_gcp.sh

cat <<EOF

PRODUCTION SECURITY BOOTSTRAP: PASS
Repo: ${REPO}
Project: ${PROJECT_ID}
Required GitHub check: ${REQUIRED_CHECK}
WIF: repository/owner numeric IDs + refs/heads/main
Long-lived SA keys: prohibited
Build staging public access: prevented
EOF
