#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO="${REPO:-brunocapellari-dotcom/AgroLogMT}"
WORKFLOW="${WORKFLOW:-full-project-final-gate.yml}"
BRANCH="${BRANCH:-$(git branch --show-current)}"
RUNNER_COUNT="${RUNNER_COUNT:-2}"
MAX_RUN_DURATION="${MAX_RUN_DURATION:-3h}"

fail() { printf 'ERRO: %s\n' "$*" >&2; exit 2; }

for cmd in git gh gcloud python3; do
  command -v "$cmd" >/dev/null 2>&1 || fail "$cmd ausente"
done

[[ -n "$BRANCH" ]] || fail "branch Git ausente"
gh auth status >/dev/null 2>&1 || fail "gh não autenticado"
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . || fail "gcloud sem conta ativa"

HEAD_SHA="$(git rev-parse HEAD)"
echo "Release candidate: branch=$BRANCH sha=$HEAD_SHA"

# Evita que um run PR antigo consuma runners destinados ao final release.
mapfile -t active_runs < <(
  gh run list     --repo "$REPO"     --workflow "$WORKFLOW"     --limit 30     --json databaseId,status,event,headSha     --jq '.[] | select((.status=="queued" or .status=="in_progress") and (.event!="workflow_dispatch" or .headSha!="'"$HEAD_SHA"'")) | .databaseId'
)
for run_id in "${active_runs[@]}"; do
  [[ -n "$run_id" ]] || continue
  echo "Cancelando run concorrente/stale: $run_id"
  gh run cancel "$run_id" --repo "$REPO" || true
done

current_dispatch="$(
  gh run list     --repo "$REPO"     --workflow "$WORKFLOW"     --limit 30     --json databaseId,status,event,headSha,url     --jq '.[] | select((.status=="queued" or .status=="in_progress") and .event=="workflow_dispatch" and .headSha=="'"$HEAD_SHA"'") | [.databaseId,.url] | @tsv'     | head -n1
)"

if [[ -z "$current_dispatch" ]]; then
  echo "Disparando final release no SHA atual..."
  gh workflow run "$WORKFLOW"     --repo "$REPO"     --ref "$BRANCH"     -f final_release=true
  sleep 3
else
  echo "Final release do SHA atual já está ativo: $current_dispatch"
fi

RUNNER_COUNT="$RUNNER_COUNT" MAX_RUN_DURATION="$MAX_RUN_DURATION"   bash scripts/create_gce_ephemeral_runner.sh

latest="$(
  gh run list     --repo "$REPO"     --workflow "$WORKFLOW"     --limit 10     --json databaseId,status,event,headSha,url     --jq '.[] | select(.event=="workflow_dispatch" and .headSha=="'"$HEAD_SHA"'") | [.databaseId,.status,.url] | @tsv'     | head -n1
)"

printf '\nFINAL RELEASE DISPATCHED\nsha=%s\nrun=%s\n' "$HEAD_SHA" "${latest:-pending-discovery}"
