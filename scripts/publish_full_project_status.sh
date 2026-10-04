#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
CONTEXT="${AGROLOG_REQUIRED_CHECK:-Whole project deterministic gate}"
FINAL_REPORT="${AGROLOG_FINAL_REPORT:-outputs/full-project-gate/FINAL.json}"
N6_RESULT="${AGROLOG_N6_RESULT:-outputs/full-project-gate/n6-result.txt}"
SHA="$(git rev-parse HEAD)"

command -v gh >/dev/null 2>&1 || { echo 'ERRO: gh ausente' >&2; exit 2; }
gh auth status >/dev/null 2>&1 || { echo 'ERRO: gh não autenticado' >&2; exit 2; }
[[ -s "$FINAL_REPORT" ]] || { echo "ERRO: relatório final ausente: $FINAL_REPORT" >&2; exit 3; }
[[ -s "$N6_RESULT" ]] || { echo "ERRO: evidência N6 ausente: $N6_RESULT" >&2; exit 3; }
grep -Fxq 'N6 CORE HOMOLOGATION: PASS' "$N6_RESULT" || { echo 'ERRO: N6 não passou' >&2; exit 3; }

python - "$FINAL_REPORT" "$SHA" <<'PY'
import json,sys
path,sha=sys.argv[1:]
obj=json.load(open(path, encoding='utf-8'))
if obj.get('status')!='PASS':
    raise SystemExit('relatório final não está PASS')
if obj.get('tested_commit')!=sha:
    raise SystemExit(f"tested_commit divergente: {obj.get('tested_commit')} != {sha}")
PY

gh api --method POST "repos/${REPO}/statuses/${SHA}" \
  -f state=success \
  -f context="$CONTEXT" \
  -f description='AgroLog full local/GCP release PASS' >/tmp/agrolog-status-publish.json

gh api "repos/${REPO}/commits/${SHA}/status" >/tmp/agrolog-status-readback.json
python - "$CONTEXT" /tmp/agrolog-status-readback.json <<'PY'
import json,sys
context,path=sys.argv[1:]
obj=json.load(open(path, encoding='utf-8'))
hits=[s for s in obj.get('statuses',[]) if s.get('context')==context]
if not hits:
    raise SystemExit(f'status ausente após publicação: {context}')
if hits[0].get('state')!='success':
    raise SystemExit(f"status não está success: {hits[0].get('state')}")
print('PASS GitHub commit status readback')
print('context=', context)
PY

printf 'AGROLOG VERIFIED STATUS: PASS\ncommit=%s\ncontext=%s\n' "$SHA" "$CONTEXT"
