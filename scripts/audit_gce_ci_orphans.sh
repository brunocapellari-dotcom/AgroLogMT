#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
MAX_AGE_MINUTES="${MAX_AGE_MINUTES:-240}"
DELETE_ORPHANS="${DELETE_ORPHANS:-0}"

[[ -n "$PROJECT_ID" && "$PROJECT_ID" != "(unset)" ]] || { echo 'ERRO: PROJECT_ID não configurado' >&2; exit 2; }
[[ "$MAX_AGE_MINUTES" =~ ^[0-9]+$ ]] || { echo 'ERRO: MAX_AGE_MINUTES inválido' >&2; exit 2; }

now_epoch="$(date -u +%s)"
found=0
deleted=0

while IFS=$'\t' read -r name zone status created; do
  [[ -n "$name" ]] || continue
  created_epoch="$(date -u -d "$created" +%s)"
  age_minutes="$(( (now_epoch - created_epoch) / 60 ))"
  printf '%s\t%s\t%s\tage_min=%s\n' "$name" "$zone" "$status" "$age_minutes"
  if (( age_minutes > MAX_AGE_MINUTES )); then
    found=$((found + 1))
    if [[ "$DELETE_ORPHANS" == "1" ]]; then
      echo "Excluindo runner órfão/expirado: $name ($zone)"
      gcloud compute instances delete "$name" --project "$PROJECT_ID" --zone "$zone" --quiet
      deleted=$((deleted + 1))
    fi
  fi
done < <(
  gcloud compute instances list     --project "$PROJECT_ID"     --filter='labels.agrolog-ci=true AND labels.github-runner=true'     --format='value(name,zone.basename(),status,creationTimestamp)'
)

echo "ORPHAN_CANDIDATES=$found"
echo "ORPHANS_DELETED=$deleted"
if (( found > 0 )) && [[ "$DELETE_ORPHANS" != "1" ]]; then
  echo "WARN: runners acima do limite; rode com DELETE_ORPHANS=1 após revisão." >&2
fi
