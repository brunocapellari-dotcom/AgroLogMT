#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
RULESET_NAME="${RULESET_NAME:-AgroLog Security Baseline}"
REQUIRED_CHECK="${REQUIRED_CHECK:-unittest}"
API_VERSION="${GITHUB_API_VERSION:-2026-03-10}"

command -v gh >/dev/null 2>&1 || { echo 'ERRO: gh ausente' >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo 'ERRO: python3 ausente' >&2; exit 2; }
gh auth status >/dev/null 2>&1 || { echo 'ERRO: gh não autenticado' >&2; exit 2; }

repo_json="$(gh api -H "X-GitHub-Api-Version: ${API_VERSION}" "repos/${REPO}")"
admin="$(printf '%s' "$repo_json" | python3 -c 'import json,sys; print(str(bool(json.load(sys.stdin).get("permissions",{}).get("admin"))).lower())')"
private="$(printf '%s' "$repo_json" | python3 -c 'import json,sys; print(str(bool(json.load(sys.stdin).get("private"))).lower())')"
default_branch="$(printf '%s' "$repo_json" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("default_branch", ""))')"

if [[ "$admin" != "true" ]]; then
  echo "ERRO: token GitHub sem permissão admin no repositório ${REPO}." >&2
  exit 3
fi
if [[ "$default_branch" != "main" ]]; then
  echo "ERRO: branch padrão inesperado: ${default_branch}; esperado main." >&2
  exit 3
fi

echo "Repo: ${REPO} (private=${private}, default=${default_branch})"

payload="$(mktemp)"
trap 'rm -f "$payload" /tmp/agrolog-rulesets.json /tmp/agrolog-ruleset-result.json' EXIT
python3 - "$RULESET_NAME" "$REQUIRED_CHECK" >"$payload" <<'PY'
import json,sys
name=sys.argv[1]
check=sys.argv[2]
payload={
    "name": name,
    "target": "branch",
    "enforcement": "active",
    "bypass_actors": [],
    "conditions": {
        "ref_name": {
            "include": ["refs/heads/main"],
            "exclude": [],
        }
    },
    "rules": [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "pull_request",
            "parameters": {
                "allowed_merge_methods": ["squash", "merge", "rebase"],
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_approving_review_count": 0,
                "required_review_thread_resolution": True,
            },
        },
        {
            "type": "required_status_checks",
            "parameters": {
                "do_not_enforce_on_create": False,
                "required_status_checks": [{"context": check}],
                "strict_required_status_checks_policy": True,
            },
        },
    ],
}
json.dump(payload, sys.stdout, ensure_ascii=False, separators=(",", ":"))
PY

gh api -H "X-GitHub-Api-Version: ${API_VERSION}" "repos/${REPO}/rulesets" > /tmp/agrolog-rulesets.json
ruleset_id="$(python3 - "$RULESET_NAME" /tmp/agrolog-rulesets.json <<'PY'
import json,sys
name=sys.argv[1]
rows=json.load(open(sys.argv[2], encoding='utf-8'))
ids=[str(r['id']) for r in rows if r.get('name') == name and r.get('source_type') == 'Repository']
if len(ids) > 1:
    raise SystemExit('mais de um ruleset canônico com o mesmo nome')
print(ids[0] if ids else '')
PY
)"

if [[ -n "$ruleset_id" ]]; then
  echo "Atualizando ruleset ${RULESET_NAME} (${ruleset_id})..."
  gh api \
    --method PUT \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    "repos/${REPO}/rulesets/${ruleset_id}" \
    --input "$payload" > /tmp/agrolog-ruleset-result.json
else
  echo "Criando ruleset ${RULESET_NAME}..."
  gh api \
    --method POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: ${API_VERSION}" \
    "repos/${REPO}/rulesets" \
    --input "$payload" > /tmp/agrolog-ruleset-result.json
  ruleset_id="$(python3 -c 'import json; print(json.load(open("/tmp/agrolog-ruleset-result.json"))["id"])')"
fi

# Readback obrigatório. Documentação não substitui a proteção real.
gh api \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: ${API_VERSION}" \
  "repos/${REPO}/rulesets/${ruleset_id}" > /tmp/agrolog-ruleset-result.json

python3 - "$RULESET_NAME" "$REQUIRED_CHECK" /tmp/agrolog-ruleset-result.json <<'PY'
import json,sys
name,check,path=sys.argv[1:]
obj=json.load(open(path, encoding='utf-8'))
errors=[]
if obj.get('name') != name:
    errors.append('nome do ruleset divergente')
if obj.get('enforcement') != 'active':
    errors.append('ruleset não está active')
ref=((obj.get('conditions') or {}).get('ref_name') or {})
if 'refs/heads/main' not in (ref.get('include') or []):
    errors.append('main não está explicitamente protegido')
rules={r.get('type'):r for r in obj.get('rules', [])}
for required in ('deletion','non_fast_forward','pull_request','required_status_checks'):
    if required not in rules:
        errors.append(f'regra ausente: {required}')
status=(rules.get('required_status_checks') or {}).get('parameters') or {}
contexts={r.get('context') for r in status.get('required_status_checks', [])}
if check not in contexts:
    errors.append(f'check obrigatório ausente: {check}')
if status.get('strict_required_status_checks_policy') is not True:
    errors.append('required status check não está strict')
pr=(rules.get('pull_request') or {}).get('parameters') or {}
if pr.get('required_review_thread_resolution') is not True:
    errors.append('review thread resolution não está obrigatória')
if obj.get('bypass_actors'):
    errors.append('ruleset possui bypass actors; baseline exige lista vazia')
if errors:
    for error in errors:
        print('FAIL', error)
    raise SystemExit(1)
print('PASS GitHub main hardening')
print('ruleset_id=', obj.get('id'))
print('required_check=', check)
print('main=protected-by-ruleset')
PY

cat <<EOF
OK: ruleset aplicado e verificado.
Repo: ${REPO}
Ruleset: ${RULESET_NAME}
Proteções: PR obrigatório, ${REQUIRED_CHECK} obrigatório/strict, conversas resolvidas, sem force-push, sem deleção, sem bypass explícito.
EOF
