#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

EXPECTED_BRANCH="fix/cloud-build-service-account-resource"
CURRENT_BRANCH="$(git branch --show-current)"
[[ "$CURRENT_BRANCH" == "$EXPECTED_BRANCH" ]] || {
  echo "ERRO: branch atual=${CURRENT_BRANCH}; esperado=${EXPECTED_BRANCH}" >&2
  exit 2
}

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERRO: existem alterações rastreadas locais antes do hardening; não vou sobrescrevê-las." >&2
  git status --short
  exit 2
fi

echo "===== Hardening GitHub workflows ====="
python scripts/harden_github_workflows.py --write
python scripts/harden_github_workflows.py
python -m unittest tests.test_workflow_zizmor_hardening -v

git add .github/workflows
if ! git diff --cached --quiet; then
  git commit -m "Harden GitHub workflows for Zizmor medium findings"
  git push origin "HEAD:${EXPECTED_BRANCH}"
else
  echo "Workflows já estavam endurecidos; nenhum commit necessário."
fi

# Reexecuta o gate integral do zero no SHA exato endurecido.
COMMIT_SHA="$(git rev-parse HEAD)"
echo "Reiniciando gate integral no commit ${COMMIT_SHA}"

bash scripts/run_agrolog_final_release.sh
