#!/usr/bin/env bash
set -euo pipefail

# Bootstrap idempotente AgroLogMT GitHub Actions -> Google Cloud, sem chave JSON.
# Execute com identidade humana administradora. Deploys recorrentes não alteram IAM/APIs/datasets.

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
POOL_ID="${POOL_ID:-github}"
PROVIDER_ID="${PROVIDER_ID:-agrologmt}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
AGRO_DATASET="${AGRO_DATASET:-agro}"
MARITIME_DATASET="${MARITIME_DATASET:-agrolog_models}"
MERCADO_DATASET="${MERCADO_DATASET:-mercado}"
HIDRO_DATASET="${HIDRO_DATASET:-hidrologia}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-agrolog-github-deployer}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
GATEWAY_SERVICE_NAME="${GATEWAY_SERVICE_NAME:-agrolog-gateway}"
CONFIGURE_ANA="${CONFIGURE_ANA:-0}"
ANA_IDENTIFICADOR_SECRET="${ANA_IDENTIFICADOR_SECRET:-agrolog-ana-identificador}"
ANA_SENHA_SECRET="${ANA_SENHA_SECRET:-agrolog-ana-senha}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: configure o projeto: gcloud config set project <PROJECT_ID>" >&2
  exit 2
fi
for cmd in gcloud bq gh; do
  command -v "$cmd" >/dev/null || { echo "ERRO: $cmd ausente" >&2; exit 2; }
done
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || {
  echo 'ERRO: nenhuma conta gcloud ativa' >&2; exit 2;
}
gh auth status >/dev/null 2>&1 || { echo 'ERRO: gh não autenticado; execute gh auth login' >&2; exit 2; }

echo "Projeto: $PROJECT_ID"
echo "Repo:    $REPO"

gcloud services enable \
  iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  bigquery.googleapis.com run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com serviceusage.googleapis.com drive.googleapis.com \
  logging.googleapis.com storage.googleapis.com secretmanager.googleapis.com \
  --project "$PROJECT_ID"

ensure_sa() {
  local name="$1" display="$2"
  local email="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  if ! gcloud iam service-accounts describe "$email" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --project "$PROJECT_ID" --display-name="$display"
  fi
}

ensure_dataset() {
  local dataset="$1"
  if bq show --project_id="$PROJECT_ID" "${PROJECT_ID}:${dataset}" >/dev/null 2>&1; then
    local actual
    actual="$(bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${dataset}" | python -c 'import json,sys; print(json.load(sys.stdin).get("location", ""))')"
    if [[ -n "$actual" && "$actual" != "$BQ_LOCATION" ]]; then
      echo "ERRO: dataset ${dataset} existe em ${actual}; esperado ${BQ_LOCATION}" >&2
      exit 3
    fi
  else
    bq --location="$BQ_LOCATION" mk --dataset "${PROJECT_ID}:${dataset}"
  fi
}

ensure_dataset_role() {
  local dataset="$1" principal="$2" role="$3"
  bq query --project_id="$PROJECT_ID" --location="$BQ_LOCATION" --use_legacy_sql=false --quiet \
    "GRANT \`${role}\` ON SCHEMA \`${PROJECT_ID}\`.${dataset} TO \"serviceAccount:${principal}\""
}

ensure_project_role() {
  local principal="$1" role="$2"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${principal}" --role="$role" --condition=None --quiet >/dev/null
}

remove_legacy_project_role() {
  local principal="$1" role="$2"
  gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${principal}" --role="$role" --condition=None --quiet >/dev/null 2>&1 || true
}

ensure_secret() {
  local name="$1" value="$2"
  if ! gcloud secrets describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud secrets create "$name" --project "$PROJECT_ID" --replication-policy=automatic >/dev/null
  fi
  printf '%s' "$value" | gcloud secrets versions add "$name" --project "$PROJECT_ID" --data-file=- >/dev/null
}

ensure_sa "$DEPLOYER_SA_NAME" "AgroLog GitHub deployer"
ensure_sa "$BUILD_SA_NAME" "AgroLog Cloud Build"
ensure_sa "$COLLECTOR_SA_NAME" "AgroLog collector runtime"
ensure_sa "$GATEWAY_SA_NAME" "AgroLog gateway runtime"

DEPLOYER_SA_EMAIL="${DEPLOYER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA_EMAIL="${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
COLLECTOR_SA_EMAIL="${COLLECTOR_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
GATEWAY_SA_EMAIL="${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
BUILD_SERVICE_AGENT="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

for role in \
  roles/serviceusage.serviceUsageAdmin \
  roles/iam.serviceAccountAdmin \
  roles/iam.serviceAccountUser \
  roles/resourcemanager.projectIamAdmin \
  roles/run.admin \
  roles/artifactregistry.admin \
  roles/storage.objectAdmin \
  roles/bigquery.admin; do
  remove_legacy_project_role "$DEPLOYER_SA_EMAIL" "$role"
done

for dataset in "$OPS_DATASET" "$LOGISTICA_DATASET" "$TRADE_DATASET" "$AGRO_DATASET" "$MARITIME_DATASET" "$MERCADO_DATASET" "$HIDRO_DATASET"; do
  ensure_dataset "$dataset"
done
if ! gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPOSITORY" \
    --repository-format=docker --location "$REGION" --project "$PROJECT_ID"
fi
if ! gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUILD_SOURCE_BUCKET}" \
    --project "$PROJECT_ID" --location "$REGION" --uniform-bucket-level-access
fi
cat >/tmp/agrolog-build-lifecycle.json <<'JSON'
{"rule":[{"action":{"type":"Delete"},"condition":{"age":7}}]}
JSON
gcloud storage buckets update "gs://${BUILD_SOURCE_BUCKET}" --lifecycle-file=/tmp/agrolog-build-lifecycle.json >/dev/null

ensure_project_role "$COLLECTOR_SA_EMAIL" roles/bigquery.user
for dataset in "$OPS_DATASET" "$LOGISTICA_DATASET" "$TRADE_DATASET" "$AGRO_DATASET" "$MARITIME_DATASET" "$MERCADO_DATASET" "$HIDRO_DATASET"; do
  ensure_dataset_role "$dataset" "$COLLECTOR_SA_EMAIL" roles/bigquery.dataEditor
done

ensure_project_role "$GATEWAY_SA_EMAIL" roles/bigquery.jobUser
ensure_dataset_role "$LOGISTICA_DATASET" "$GATEWAY_SA_EMAIL" roles/bigquery.dataViewer
ensure_dataset_role "$MARITIME_DATASET" "$GATEWAY_SA_EMAIL" roles/bigquery.dataViewer

ensure_project_role "$BUILD_SA_EMAIL" roles/logging.logWriter
gcloud artifacts repositories add-iam-policy-binding "$AR_REPOSITORY" \
  --location "$REGION" --project "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA_EMAIL}" --role=roles/artifactregistry.writer --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_SOURCE_BUCKET}" \
  --member="serviceAccount:${BUILD_SA_EMAIL}" --role=roles/storage.objectViewer --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_SOURCE_BUCKET}" \
  --member="serviceAccount:${BUILD_SA_EMAIL}" --role=roles/storage.bucketViewer --quiet >/dev/null

gcloud iam service-accounts add-iam-policy-binding "$BUILD_SA_EMAIL" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SERVICE_AGENT}" \
  --role=roles/iam.serviceAccountTokenCreator --quiet >/dev/null

for role in roles/serviceusage.serviceUsageConsumer roles/cloudbuild.builds.editor roles/run.developer; do
  ensure_project_role "$DEPLOYER_SA_EMAIL" "$role"
done
gcloud artifacts repositories add-iam-policy-binding "$AR_REPOSITORY" \
  --location "$REGION" --project "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_SA_EMAIL}" --role=roles/artifactregistry.reader --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_SOURCE_BUCKET}" \
  --member="serviceAccount:${DEPLOYER_SA_EMAIL}" --role=roles/storage.objectUser --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUILD_SOURCE_BUCKET}" \
  --member="serviceAccount:${DEPLOYER_SA_EMAIL}" --role=roles/storage.bucketViewer --quiet >/dev/null

for sa in "$BUILD_SA_EMAIL" "$COLLECTOR_SA_EMAIL" "$GATEWAY_SA_EMAIL"; do
  gcloud iam service-accounts add-iam-policy-binding "$sa" \
    --project "$PROJECT_ID" \
    --member="serviceAccount:${DEPLOYER_SA_EMAIL}" \
    --role=roles/iam.serviceAccountUser --quiet >/dev/null
done

if gcloud run services describe "$GATEWAY_SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud run services update "$GATEWAY_SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" --invoker-iam-check --quiet >/dev/null
  gcloud run services remove-iam-policy-binding "$GATEWAY_SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" \
    --member=allUsers --role=roles/run.invoker --quiet >/dev/null 2>&1 || true
fi

if ! gcloud iam workload-identity-pools describe "$POOL_ID" --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" --location=global --project "$PROJECT_ID" --display-name="GitHub Actions"
fi
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --workload-identity-pool="$POOL_ID" --location=global --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --workload-identity-pool="$POOL_ID" --location=global --project "$PROJECT_ID" \
    --display-name="AgroLogMT GitHub" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${REPO}' && assertion.ref=='refs/heads/main'"
fi

PROVIDER_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA_EMAIL" \
  --project "$PROJECT_ID" --role=roles/iam.workloadIdentityUser --member="$PRINCIPAL" --quiet >/dev/null

printf '%s' "$PROVIDER_RESOURCE" | gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "$REPO"
printf '%s' "$DEPLOYER_SA_EMAIL" | gh secret set GCP_SERVICE_ACCOUNT --repo "$REPO"
printf '%s' "$DEPLOYER_SA_EMAIL" | gh secret set GCP_DEPLOYER_SERVICE_ACCOUNT --repo "$REPO"
printf '%s' "$BUILD_SA_EMAIL" | gh secret set GCP_BUILD_SERVICE_ACCOUNT --repo "$REPO"
printf '%s' "$BUILD_SOURCE_BUCKET" | gh secret set GCP_BUILD_SOURCE_BUCKET --repo "$REPO"
printf '%s' "$PROJECT_ID" | gh secret set GCP_PROJECT_ID --repo "$REPO"

if [[ "$CONFIGURE_ANA" == "1" ]]; then
  printf 'ANA HidroWeb identificador: '
  IFS= read -r ANA_ID
  printf 'ANA HidroWeb senha (não será exibida): '
  IFS= read -rs ANA_PASSWORD
  printf '\n'
  if [[ -z "$ANA_ID" || -z "$ANA_PASSWORD" ]]; then
    echo 'ERRO: credenciais ANA não preenchidas.' >&2
    exit 2
  fi

  # Nomes canônicos consumidos pelo CI e pelo runtime.
  printf '%s' "$ANA_ID" | gh secret set ANA_IDENTIFICADOR --repo "$REPO"
  printf '%s' "$ANA_PASSWORD" | gh secret set ANA_SENHA --repo "$REPO"

  # Secret Manager é a origem dos segredos do Cloud Run; GitHub recebe somente
  # os aliases necessários ao probe opcional de CI.
  ensure_secret "$ANA_IDENTIFICADOR_SECRET" "$ANA_ID"
  ensure_secret "$ANA_SENHA_SECRET" "$ANA_PASSWORD"
  for secret in "$ANA_IDENTIFICADOR_SECRET" "$ANA_SENHA_SECRET"; do
    gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT_ID" \
      --member="serviceAccount:${COLLECTOR_SA_EMAIL}" --role=roles/secretmanager.secretAccessor --quiet >/dev/null
  done
  unset ANA_PASSWORD ANA_ID
fi

echo
printf 'OK: bootstrap GCP/WIF concluído sem chave JSON.\n'
printf 'Deployer:           %s\n' "$DEPLOYER_SA_EMAIL"
printf 'Builder:            %s\n' "$BUILD_SA_EMAIL"
printf 'Collector:          %s\n' "$COLLECTOR_SA_EMAIL"
printf 'Gateway:            %s\n' "$GATEWAY_SA_EMAIL"
printf 'Build staging:      gs://%s\n' "$BUILD_SOURCE_BUCKET"
printf 'Datasets:           %s, %s, %s, %s, %s, %s, %s\n' "$OPS_DATASET" "$LOGISTICA_DATASET" "$TRADE_DATASET" "$AGRO_DATASET" "$MARITIME_DATASET" "$MERCADO_DATASET" "$HIDRO_DATASET"
printf 'IMPORTANTE: compartilhe a pasta RAW do Drive como Editor somente com %s.\n' "$COLLECTOR_SA_EMAIL"
printf 'Deploy/homologação recorrente não deve alterar IAM, APIs ou criar datasets.\n'
