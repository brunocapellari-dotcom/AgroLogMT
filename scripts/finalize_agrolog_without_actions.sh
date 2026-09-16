#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OUT="${AGROLOG_FINAL_OUT:-outputs/full-project-gate}"
N6_DIR="${EVIDENCE_DIR:-outputs/n6-core}"

if [[ -z "$PROJECT_ID" || "$PROJECT_ID" == "(unset)" ]]; then
  echo "ERRO: PROJECT_ID ausente" >&2
  exit 2
fi

for cmd in bash python git curl tar sha256sum npm node docker gcloud bq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERRO: comando obrigatório ausente: $cmd" >&2; exit 2; }
done

gcloud config set project "$PROJECT_ID" >/dev/null
ACTIVE_ACCOUNT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
[[ -n "$ACTIVE_ACCOUNT" ]] || { echo "ERRO: nenhuma conta gcloud ativa" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "ERRO: Docker daemon indisponível; gate final não pode provar builds/imagens" >&2; exit 2; }

mkdir -p "$OUT" "$N6_DIR"
COMMIT_SHA="$(git rev-parse HEAD)"
BRANCH="$(git branch --show-current)"
printf 'project=%s\nregion=%s\ncommit=%s\nbranch=%s\nactive_account=%s\n' \
  "$PROJECT_ID" "$REGION" "$COMMIT_SHA" "$BRANCH" "$ACTIVE_ACCOUNT" \
  > "$OUT/local-final-run-metadata.txt"

echo "===== 1/11 Gate determinístico de 100% do repositório ====="
bash scripts/run_full_project_ci_local.sh

echo "===== 2/11 Auditoria GitHub Actions em severidade final ====="
zizmor --offline --persona=auditor --min-severity=medium . | tee "$OUT/zizmor-final.txt"

echo "===== 3/11 Gitleaks em todo o histórico Git ====="
if [[ ! -x /tmp/gitleaks ]]; then
  GITLEAKS_URL='https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz'
  GITLEAKS_SHA='551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
  curl --proto '=https' --tlsv1.2 -fsSLo /tmp/gitleaks.tar.gz "$GITLEAKS_URL"
  echo "${GITLEAKS_SHA}  /tmp/gitleaks.tar.gz" | sha256sum -c -
  tar -xzf /tmp/gitleaks.tar.gz -C /tmp gitleaks
fi
/tmp/gitleaks git --redact --no-banner --exit-code 1 .
printf 'GITLEAKS HISTORY PASS\nversion=8.30.1\ncommit=%s\n' "$COMMIT_SHA" > "$OUT/gitleaks.txt"

install_trivy() {
  local version='0.74.0'
  local archive="trivy_${version}_Linux-64bit.tar.gz"
  local base="https://github.com/aquasecurity/trivy/releases/download/v${version}"
  local checksums="trivy_${version}_checksums.txt"
  local checksums_sha='bc701c3c3ee8b9acbea2c23257e41381e3854888f51281616a6ba5dc96963821'
  curl --proto '=https' --tlsv1.2 -fsSLo "/tmp/${checksums}" "${base}/${checksums}"
  echo "${checksums_sha}  /tmp/${checksums}" | sha256sum -c -
  curl --proto '=https' --tlsv1.2 -fsSLo "/tmp/${archive}" "${base}/${archive}"
  (cd /tmp && grep -F "  ${archive}" "${checksums}" | sha256sum -c -)
  tar -xzf "/tmp/${archive}" -C /tmp trivy
}

install_syft() {
  local version='1.51.1'
  local archive="syft_${version}_linux_amd64.tar.gz"
  local base="https://github.com/anchore/syft/releases/download/v${version}"
  local checksums="syft_${version}_checksums.txt"
  local checksums_sha='105346699e7cb694afa37a21e2386432df6278c99f71331c24b1e0bb0f38cc75'
  curl --proto '=https' --tlsv1.2 -fsSLo "/tmp/${checksums}" "${base}/${checksums}"
  echo "${checksums_sha}  /tmp/${checksums}" | sha256sum -c -
  curl --proto '=https' --tlsv1.2 -fsSLo "/tmp/${archive}" "${base}/${archive}"
  (cd /tmp && grep -F "  ${archive}" "${checksums}" | sha256sum -c -)
  tar -xzf "/tmp/${archive}" -C /tmp syft
}

echo "===== 4/11 Trivy filesystem + IaC ====="
install_trivy
/tmp/trivy fs \
  --scanners vuln,misconfig \
  --severity HIGH,CRITICAL \
  --ignore-unfixed=false \
  --exit-code 1 \
  --format table \
  --output "$OUT/trivy-fs.txt" .

echo "===== 5/11 Build de todos os containers de produção ====="
docker build --pull --tag agrolog-collector:gate .
docker build --pull --file gateway/Dockerfile --tag agrolog-gateway:gate .
printf 'CONTAINERS PASS\nagrolog-collector:gate\nagrolog-gateway:gate\ncommit=%s\n' "$COMMIT_SHA" > "$OUT/containers.txt"

echo "===== 6/11 Trivy nas imagens ====="
/tmp/trivy image --severity HIGH,CRITICAL --ignore-unfixed=false --exit-code 1 --format table --output "$OUT/trivy-collector.txt" agrolog-collector:gate
/tmp/trivy image --severity HIGH,CRITICAL --ignore-unfixed=false --exit-code 1 --format table --output "$OUT/trivy-gateway.txt" agrolog-gateway:gate
cat "$OUT/trivy-collector.txt" "$OUT/trivy-gateway.txt" >> "$OUT/trivy-fs.txt"

echo "===== 7/11 SBOM source + imagens ====="
install_syft
/tmp/syft dir:. -o "spdx-json=${OUT}/source.spdx.json"
/tmp/syft agrolog-collector:gate -o "spdx-json=${OUT}/collector.spdx.json"
/tmp/syft agrolog-gateway:gate -o "spdx-json=${OUT}/gateway.spdx.json"

echo "===== 8/11 Preflight GCP e segurança runtime ====="
PROJECT_ID="$PROJECT_ID" REGION="$REGION" BQ_LOCATION="$BQ_LOCATION" \
  bash scripts/preflight_n6_gcp.sh | tee "$OUT/gcp-preflight.txt"
cp "$OUT/gcp-preflight.txt" "$OUT/runtime-security.txt"

echo "===== 9/11 Homologação N6 completa ====="
PROJECT_ID="$PROJECT_ID" REGION="$REGION" BQ_LOCATION="$BQ_LOCATION" EVIDENCE_DIR="$N6_DIR" \
  bash scripts/homologate_n6_core.sh
N6_RESULT="$(find "$N6_DIR" -name RESULT.txt -type f -print | sort | tail -n 1)"
[[ -n "$N6_RESULT" ]] || { echo "ERRO: resultado N6 ausente" >&2; exit 3; }
grep -Fxq 'N6 CORE HOMOLOGATION: PASS' "$N6_RESULT"
cp "$N6_RESULT" "$OUT/n6-result.txt"

echo "===== 10/11 Restore drill não destrutivo ====="
python scripts/run_bigquery_restore_drill.py \
  --project "$PROJECT_ID" \
  --location "$BQ_LOCATION" \
  --output "$OUT/restore-drill.json"

echo "===== 11/11 Gate LIVE + auditor independente + selo final ====="
export AGROLOG_EVIDENCE_CONTAINERS="$OUT/containers.txt"
export AGROLOG_EVIDENCE_GITLEAKS="$OUT/gitleaks.txt"
export AGROLOG_EVIDENCE_TRIVY="$OUT/trivy-fs.txt"
export AGROLOG_EVIDENCE_SBOM="$OUT/source.spdx.json"
export AGROLOG_EVIDENCE_RUNTIME_SECURITY="$OUT/runtime-security.txt"
export AGROLOG_EVIDENCE_DATA_QUALITY="$OUT/n6-result.txt"
export AGROLOG_EVIDENCE_RESTORE="$OUT/restore-drill.json"
export AGROLOG_EVIDENCE_GCP_PREFLIGHT="$OUT/gcp-preflight.txt"
export AGROLOG_EVIDENCE_N6_CORE="$OUT/n6-result.txt"

set +e
python scripts/validate_full_project.py --mode final --report "$OUT/pre-audit.json"
PRE_CODE=$?
set -e
[[ "$PRE_CODE" -eq 2 ]] || { echo "ERRO: pre-audit deveria bloquear apenas pelo auditor pendente; code=${PRE_CODE}" >&2; exit 4; }

python - "$OUT/pre-audit.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1], encoding='utf-8'))
for name in ('tests_deterministic_all','tests_live_all'):
    item=next(stage for stage in report['stages'] if stage['name']==name)
    if item['details'].get('skipped',0):
        raise SystemExit(f'{name} possui skipped; release final exige zero skips')
pending=[stage['name'] for stage in report['stages'] if stage['status']!='PASS' and stage['name']!='final_auditor']
if pending:
    raise SystemExit(f'estágios não aprovados antes do auditor: {pending}')
PY

python scripts/final_release_auditor.py "$OUT/pre-audit.json" --output "$OUT/final-auditor.json"

python - "$OUT/pre-audit.json" "$OUT/final-auditor.json" "$OUT/FINAL.json" <<'PY'
import json,sys
from datetime import datetime,timezone
from pathlib import Path
from models.project_release_gate import ReleaseStage,evaluate_release
pre=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
aud=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
if aud.get('status')!='PASS':
    raise SystemExit('final auditor did not PASS')
stages=[]
for item in pre['stages']:
    if item['name']=='final_auditor':
        item={'name':'final_auditor','status':'PASS','evidence':[sys.argv[2]],'details':{'audited_at':datetime.now(timezone.utc).isoformat()}}
    stages.append(item)
evaluation=evaluate_release([ReleaseStage.from_dict(item) for item in stages])
final=dict(pre)
final['stages']=stages
final['evaluation']=evaluation
final['status']=evaluation['status']
final['blockers']=[]
final['failures']=[]
final['sealed_at']=datetime.now(timezone.utc).isoformat()
final['tested_commit']=__import__('subprocess').check_output(['git','rev-parse','HEAD'], text=True).strip()
Path(sys.argv[3]).write_text(json.dumps(final,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
if final['status']!='PASS':
    raise SystemExit(f"FINAL RELEASE BLOCKED: {final['status']}")
PY

printf '\nN6 CORE HOMOLOGATION: PASS\n'
printf 'AGROLOG MT FINAL RELEASE: PASS\n'
printf 'tested_commit=%s\n' "$COMMIT_SHA"
printf 'final_report=%s/FINAL.json\n' "$OUT"
