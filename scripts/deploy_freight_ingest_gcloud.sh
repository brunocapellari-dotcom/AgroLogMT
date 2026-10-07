#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
LOGISTICA_DATASET="${LOGISTICA_DATASET:-logistica}"
AR_REPOSITORY="${AR_REPOSITORY:-agrolog}"
BUILD_SOURCE_BUCKET="${BUILD_SOURCE_BUCKET:-${PROJECT_ID}-agrolog-build-source}"
BUILD_SA_NAME="${BUILD_SA_NAME:-agrolog-builder}"
FREIGHT_INGEST_SA_NAME="${FREIGHT_INGEST_SA_NAME:-agrolog-freight-ingest}"
FREIGHT_SERVICE_NAME="${FREIGHT_SERVICE_NAME:-agrolog-freight-ingest}"
FREIGHT_SECRET_NAME="${FREIGHT_SECRET_NAME:-agrolog-freight-shared-secret}"
IMAGE_NAME="${FREIGHT_IMAGE_NAME:-freight-ingest}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
MAX_INSTANCES="${FREIGHT_MAX_INSTANCES:-3}"
CONCURRENCY="${FREIGHT_CONCURRENCY:-20}"
REQUEST_TIMEOUT="${FREIGHT_REQUEST_TIMEOUT:-30}"
MEMORY="${FREIGHT_MEMORY:-512Mi}"
CPU="${FREIGHT_CPU:-1}"
BQ_MAX_BYTES_BILLED="${AGROLOG_FREIGHT_BQ_MAX_BYTES_BILLED:-100000000}"
BQ_QUERY_TIMEOUT_SECONDS="${AGROLOG_FREIGHT_BQ_QUERY_TIMEOUT_SECONDS:-15}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: projeto GCP não configurado" >&2
  exit 2
fi
for cmd in gcloud bq python3; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERRO: $cmd ausente" >&2
    exit 2
  }
done
for value in "$MAX_INSTANCES" "$CONCURRENCY" "$REQUEST_TIMEOUT" "$BQ_MAX_BYTES_BILLED" "$BQ_QUERY_TIMEOUT_SECONDS"; do
  [[ "$value" =~ ^[0-9]+$ ]] || {
    echo "ERRO: limite numérico inválido: $value" >&2
    exit 2
  }
done
[[ "$MAX_INSTANCES" -ge 1 && "$MAX_INSTANCES" -le 20 ]] || {
  echo "ERRO: FREIGHT_MAX_INSTANCES fora do limite 1..20" >&2
  exit 2
}
[[ "$CONCURRENCY" -ge 1 && "$CONCURRENCY" -le 100 ]] || {
  echo "ERRO: FREIGHT_CONCURRENCY fora do limite 1..100" >&2
  exit 2
}
[[ "$REQUEST_TIMEOUT" -ge 5 && "$REQUEST_TIMEOUT" -le 120 ]] || {
  echo "ERRO: FREIGHT_REQUEST_TIMEOUT fora do limite 5..120" >&2
  exit 2
}

FREIGHT_INGEST_SA_EMAIL="${FREIGHT_INGEST_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SERVICE_ACCOUNT="${BUILD_SERVICE_ACCOUNT:-${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${IMAGE_NAME}:${IMAGE_TAG}"

gcloud config set project "$PROJECT_ID" >/dev/null

gcloud iam service-accounts describe "$FREIGHT_INGEST_SA_EMAIL"   --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: service account de frete ausente; execute bootstrap administrativo" >&2
  exit 3
}
gcloud iam service-accounts describe "$BUILD_SERVICE_ACCOUNT"   --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: build service account ausente" >&2
  exit 3
}
gcloud secrets describe "$FREIGHT_SECRET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: secret de HMAC de frete ausente; execute bootstrap administrativo" >&2
  exit 3
}
gcloud secrets versions list "$FREIGHT_SECRET_NAME" --project "$PROJECT_ID"   --filter='state=ENABLED' --format='value(name)' | grep -q . || {
  echo "ERRO: secret de HMAC não possui versão ENABLED" >&2
  exit 3
}
bq show --project_id="$PROJECT_ID"   "${PROJECT_ID}:${LOGISTICA_DATASET}.freight_events" >/dev/null 2>&1 || {
  echo "ERRO: tabela freight_events ausente; execute bootstrap administrativo" >&2
  exit 3
}
gcloud artifacts repositories describe "$AR_REPOSITORY"   --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: Artifact Registry ausente" >&2
  exit 3
}
gcloud storage buckets describe "gs://${BUILD_SOURCE_BUCKET}"   --project "$PROJECT_ID" >/dev/null 2>&1 || {
  echo "ERRO: staging bucket ausente" >&2
  exit 3
}

gcloud builds submit .   --project "$PROJECT_ID"   --service-account "$BUILD_SERVICE_ACCOUNT"   --gcs-source-staging-dir "gs://${BUILD_SOURCE_BUCKET}/source"   --config gateway/cloudbuild.yaml   --substitutions "_IMAGE=${IMAGE}"

gcloud run deploy "$FREIGHT_SERVICE_NAME"   --image "$IMAGE"   --region "$REGION"   --project "$PROJECT_ID"   --service-account "$FREIGHT_INGEST_SA_EMAIL"   --execution-environment gen2   --cpu "$CPU"   --memory "$MEMORY"   --max-instances "$MAX_INSTANCES"   --concurrency "$CONCURRENCY"   --timeout "${REQUEST_TIMEOUT}s"   --no-allow-unauthenticated   --command uvicorn   --args "gateway.freight_app:app,--host,0.0.0.0,--port,8080"   --set-env-vars "AGROLOG_GCP_PROJECT=${PROJECT_ID},AGROLOG_FREIGHT_DATASET=${LOGISTICA_DATASET},AGROLOG_BQ_LOCATION=${BQ_LOCATION},AGROLOG_BQ_MAX_BYTES_BILLED=${BQ_MAX_BYTES_BILLED},AGROLOG_BQ_QUERY_TIMEOUT_SECONDS=${BQ_QUERY_TIMEOUT_SECONDS}"   --update-secrets "AGROLOG_FREIGHT_SHARED_SECRET=${FREIGHT_SECRET_NAME}:latest"   --startup-probe "httpGet.path=/readyz,httpGet.port=8080,initialDelaySeconds=1,failureThreshold=10,timeoutSeconds=3,periodSeconds=3"   --readiness-probe "httpGet.path=/readyz,httpGet.port=8080,successThreshold=1,failureThreshold=3,timeoutSeconds=3,periodSeconds=5"   --liveness-probe "httpGet.path=/healthz,httpGet.port=8080,initialDelaySeconds=5,failureThreshold=3,timeoutSeconds=3,periodSeconds=10"

for broad_member in allUsers allAuthenticatedUsers; do
  gcloud run services remove-iam-policy-binding "$FREIGHT_SERVICE_NAME"     --region "$REGION" --project "$PROJECT_ID"     --member="$broad_member" --role=roles/run.invoker --quiet >/dev/null 2>&1 || true
done

service_json="$(mktemp)"
trap 'rm -f "$service_json"' EXIT
gcloud run services describe "$FREIGHT_SERVICE_NAME"   --region "$REGION" --project "$PROJECT_ID" --format=json >"$service_json"
python3 - "$service_json" "$FREIGHT_INGEST_SA_EMAIL" <<'PY'
import json
import sys

path, expected_sa = sys.argv[1:]
service = json.load(open(path, encoding="utf-8"))
template = service.get("spec", {}).get("template", {}).get("spec", {})
actual_sa = template.get("serviceAccountName")
if actual_sa != expected_sa:
    raise SystemExit(f"unexpected runtime service account: {actual_sa!r}")

status = service.get("status", {})
conditions = {
    item.get("type"): item.get("status")
    for item in status.get("conditions", [])
}
if conditions.get("Ready") != "True":
    raise SystemExit(f"Cloud Run service not Ready: {conditions}")

created = status.get("latestCreatedRevisionName")
ready = status.get("latestReadyRevisionName")
if not created or created != ready:
    raise SystemExit(
        f"latest revision is not ready: created={created!r} ready={ready!r}"
    )
print(f"FREIGHT_INGEST_DEPLOY_PASS revision={ready}")
PY

broad_binding="$(gcloud run services get-iam-policy "$FREIGHT_SERVICE_NAME"   --region "$REGION" --project "$PROJECT_ID"   --flatten='bindings[].members'   --filter='bindings.role=roles/run.invoker AND (bindings.members=allUsers OR bindings.members=allAuthenticatedUsers)'   --format='value(bindings.members)' | head -n1)"
if [[ "$broad_binding" == "allUsers" || "$broad_binding" == "allAuthenticatedUsers" ]]; then
  echo "ERRO: serviço de frete ficou publicamente invocável" >&2
  exit 4
fi

echo "Freight ingest implantado com identidade dedicada e Cloud Run IAM privado."
echo "Runtime identity: ${FREIGHT_INGEST_SA_EMAIL}"
echo "Secret: ${FREIGHT_SECRET_NAME} (valor não exibido)"
echo "BigQuery target: ${PROJECT_ID}.${LOGISTICA_DATASET}.freight_events"
