#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/finalize_agrolog_without_actions.sh
bash scripts/publish_full_project_status.sh

echo 'AGROLOG MT PRIVATE-REPO FINALIZATION: PASS'
