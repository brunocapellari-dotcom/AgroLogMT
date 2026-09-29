#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
[[ -n "$PROJECT_ID" && "$PROJECT_ID" != "(unset)" ]] || { echo 'ERRO: PROJECT_ID não configurado' >&2; exit 2; }

gcloud config set project "$PROJECT_ID" >/dev/null
mapfile -t instances < <(
  gcloud compute instances list \
    --project "$PROJECT_ID" \
    --filter='labels.agrolog-ci=true AND labels.github-runner=true' \
    --format='value(name,zone.basename())'
)

if [[ "${#instances[@]}" -eq 0 ]]; then
  echo 'Nenhuma VM de runner AgroLog encontrada.'
  exit 0
fi

for row in "${instances[@]}"; do
  read -r name zone <<<"$row"
  echo "Excluindo ${name} (${zone})..."
  gcloud compute instances delete "$name" --project "$PROJECT_ID" --zone "$zone" --quiet
done

echo 'OK: VMs de CI efêmero removidas.'
