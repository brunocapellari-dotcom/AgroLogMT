#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OPS_DATASET="${OPS_DATASET:-agrolog_ops}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
TRADE_DATASET="${TRADE_DATASET:-comercio_exterior}"
AGRO_DATASET="${AGRO_DATASET:-agro}"
MARITIME_DATASET="${MARITIME_DATASET:-agrolog_models}"
MERCADO_DATASET="${MERCADO_DATASET:-mercado}"
HIDRO_DATASET="${HIDRO_DATASET:-hidrologia}"
COLLECTOR_SA_NAME="${COLLECTOR_SA_NAME:-agrolog-collector}"
GATEWAY_SA_NAME="${GATEWAY_SA_NAME:-agrolog-gateway}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
DEPLOYER_SA_NAME="${DEPLOYER_SA_NAME:-agrolog-github-deployer}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
RAW_BUCKET="${RAW_BUCKET:-${PROJECT_ID}-agrolog-raw}"
POOL_ID="${POOL_ID:-github}"
PROVIDER_ID="${PROVIDER_ID:-agrologmt}"
GATEWAY_SERVICE_NAME="${GATEWAY_SERVICE_NAME:-agrolog-gateway}"

failures=0
warnings=0
ok() { printf 'OK   %s\n' "$*"; }
warn() { printf 'WARN %s\n' "$*"; warnings=$((warnings+1)); }
fail() { printf 'FAIL %s\n' "$*"; failures=$((failures+1)); }

command -v gcloud >/dev/null 2>&1 || { echo 'gcloud ausente' >&2; exit 2; }
command -v bq >/dev/null 2>&1 || { echo 'bq ausente' >&2; exit 2; }
if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo 'Projeto GCP não configurado.' >&2
  exit 2
fi

ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] && ok "conta ativa: $ACTIVE_ACCOUNT" || fail 'nenhuma conta gcloud ativa'
ok "projeto: $PROJECT_ID"
ok "região Cloud Run: $REGION"
ok "localização BigQuery esperada: $BQ_LOCATION"

for api in \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  bigquery.googleapis.com drive.googleapis.com iam.googleapis.com storage.googleapis.com \
  iamcredentials.googleapis.com sts.googleapis.com logging.googleapis.com secretmanager.googleapis.com; do
  if gcloud services list --enabled --project "$PROJECT_ID" --filter="config.name=$api" --format='value(config.name)' | grep -qx "$api"; then
    ok "API habilitada: $api"
  else
    fail "API não habilitada: $api"
  fi
done

for dataset in "$OPS_DATASET" "$LOGISTICA_DATASET" "$TRADE_DATASET" "$AGRO_DATASET" "$MARITIME_DATASET" "$MERCADO_DATASET" "$HIDRO_DATASET"; do
  tmp="/tmp/agrolog-dataset-${dataset}.json"
  if bq show --project_id="$PROJECT_ID" --format=prettyjson "${PROJECT_ID}:${dataset}" >"$tmp" 2>/dev/null; then
    actual_location="$(python - "$tmp" <<'PY'
import json,sys
print(json.load(open(sys.argv[1])).get('location',''))
PY
)"
    if [[ -n "$actual_location" && "$actual_location" != "$BQ_LOCATION" ]]; then
      fail "dataset ${dataset} está em ${actual_location}, esperado ${BQ_LOCATION}"
    else
      ok "dataset existente: ${dataset} (${actual_location:-localização não informada})"
    fi
  else
    fail "dataset obrigatório ausente: ${dataset}; execute o bootstrap administrativo"
  fi
done

SA_EMAILS=()
for name in "$DEPLOYER_SA_NAME" "$BUILD_SA_NAME" "$COLLECTOR_SA_NAME" "$GATEWAY_SA_NAME"; do
  sa="${name}@${PROJECT_ID}.iam.gserviceaccount.com"
  SA_EMAILS+=("$sa")
  if gcloud iam service-accounts describe "$sa" --project "$PROJECT_ID" >/dev/null 2>&1; then
    ok "service account existe: $sa"
    if user_keys="$(gcloud iam service-accounts keys list \
      --iam-account="$sa" --managed-by=user --project "$PROJECT_ID" --format='value(name)' 2>/dev/null)"; then
      if [[ -n "$user_keys" ]]; then
        fail "service account possui chave gerenciada por usuário (proibida): $sa"
      else
        ok "sem chave de longa duração gerenciada por usuário: $sa"
      fi
    else
      fail "não foi possível inspecionar chaves da service account: $sa"
    fi
  else
    fail "service account obrigatória ausente: $sa"
  fi
done

# Runtime identities não podem carregar papéis administrativos genéricos no projeto.
policy_file="/tmp/agrolog-project-iam.json"
gcloud projects get-iam-policy "$PROJECT_ID" --format=json >"$policy_file"
python - "$policy_file" "$PROJECT_ID" "${SA_EMAILS[@]}" <<'PY' || failures=$((failures+1))
import json,sys
policy=json.load(open(sys.argv[1], encoding='utf-8'))
project=sys.argv[2]
services=set(sys.argv[3:])
forbidden={
    'roles/owner','roles/editor','roles/bigquery.admin','roles/resourcemanager.projectIamAdmin',
    'roles/iam.serviceAccountAdmin','roles/serviceusage.serviceUsageAdmin','roles/run.admin',
}
hits=[]
for binding in policy.get('bindings', []):
    role=binding.get('role')
    if role not in forbidden:
        continue
    for member in binding.get('members', []):
        if member.startswith('serviceAccount:') and member.split(':',1)[1] in services:
            hits.append((member, role))
if hits:
    for member,role in hits:
        print(f'FAIL privilégio administrativo excessivo no projeto {project}: {member} -> {role}')
    raise SystemExit(1)
print('OK   nenhuma service account AgroLog possui papel administrativo genérico proibido no projeto')
PY

if gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --workload-identity-pool="$POOL_ID" --location=global --project "$PROJECT_ID" --format=json \
  > /tmp/agrolog-wif-provider.json 2>/dev/null; then
  if python - /tmp/agrolog-wif-provider.json <<'PY'
import json,sys
obj=json.load(open(sys.argv[1], encoding='utf-8'))
condition=str(obj.get('attributeCondition') or '')
mapping=obj.get('attributeMapping') or {}
required_condition=('assertion.repository_id','assertion.repository_owner_id','refs/heads/main')
required_mapping=('attribute.repository_id','attribute.repository_owner_id','attribute.ref')
missing=[x for x in required_condition if x not in condition]
missing += [x for x in required_mapping if x not in mapping]
if missing:
    print('WIF_MISSING=' + ','.join(missing))
    raise SystemExit(1)
PY
  then
    ok "WIF provider usa IDs imutáveis do GitHub e restringe main"
  else
    fail "WIF provider não atende baseline de IDs imutáveis/main; reexecute bootstrap"
  fi
else
  fail "WIF provider ausente: ${POOL_ID}/${PROVIDER_ID}"
fi

if gcloud artifacts repositories describe "$AR_REPOSITORY" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Artifact Registry: $AR_REPOSITORY"
else
  fail "Artifact Registry ausente: $AR_REPOSITORY"
fi
if gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Build staging bucket: gs://${BUILD_SOURCE_BUCKET}"
else
  fail "Build staging bucket ausente: gs://${BUILD_SOURCE_BUCKET}"
fi

if gcloud storage buckets describe "gs://${RAW_BUCKET}" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "RAW operacional bucket: gs://${RAW_BUCKET}"
else
  fail "RAW operacional bucket ausente: gs://${RAW_BUCKET}; execute scripts/setup_raw_gcs.sh"
fi

for job in agrolog-dados agrolog-radar agrolog-conhecimento; do
  if gcloud run jobs describe "$job" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
    ok "Cloud Run Job existente: $job"
  else
    warn "Cloud Run Job ainda não implantado: $job"
  fi
done

GATEWAY_SA_EMAIL="${GATEWAY_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud run services describe "$GATEWAY_SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1; then
  ok "Cloud Run service existente: $GATEWAY_SERVICE_NAME"
  gateway_sa="$(gcloud run services describe "$GATEWAY_SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" --format='value(spec.template.spec.serviceAccountName)')"
  if [[ "$gateway_sa" == "$GATEWAY_SA_EMAIL" ]]; then
    ok "Gateway usa service account dedicada"
  else
    fail "Gateway usa service account inesperada: ${gateway_sa:-<vazia>}"
  fi
  broad_binding="$(gcloud run services get-iam-policy "$GATEWAY_SERVICE_NAME" \
    --region "$REGION" --project "$PROJECT_ID" \
    --flatten='bindings[].members' \
    --filter='bindings.role=roles/run.invoker AND (bindings.members=allUsers OR bindings.members=allAuthenticatedUsers)' \
    --format='value(bindings.members)' | head -n1)"
  if [[ "$broad_binding" == "allUsers" || "$broad_binding" == "allAuthenticatedUsers" ]]; then
    fail "Gateway possui invocação ampla: ${broad_binding}/roles.run.invoker"
  else
    ok "Gateway sem allUsers/allAuthenticatedUsers em roles.run.invoker"
  fi
else
  warn 'AgroLog Gateway ainda não implantado'
fi

printf '\nResumo: failures=%d warnings=%d\n' "$failures" "$warnings"
[[ "$failures" -eq 0 ]]
