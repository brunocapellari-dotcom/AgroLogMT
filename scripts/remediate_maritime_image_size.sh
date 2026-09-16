#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="$(git branch --show-current)"
[[ "$BRANCH" == "fix/cloud-build-service-account-resource" ]] || {
  echo "ERRO: branch inesperada: $BRANCH" >&2
  exit 2
}

mkdir -p outputs/full-project-gate

echo "===== Remediação image-size CVE-2025-71329 / CVE-2025-71330 ====="
cd maritime_ui
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
npm ci --ignore-scripts --no-audit --no-fund
npm run build

python - <<'PY'
import json
from pathlib import Path
lock = json.loads(Path('package-lock.json').read_text(encoding='utf-8'))
pkgs = lock.get('packages', {})
entry = pkgs.get('node_modules/image-size')
if not entry:
    raise SystemExit('ERRO: node_modules/image-size ausente após override; lockfile inesperado')
version = str(entry.get('version', ''))
name = str(entry.get('name', ''))
if version == '0.7.5':
    raise SystemExit('ERRO: image-size 0.7.5 vulnerável ainda presente no lockfile')
if version != '2.1.0' or name not in {'', 'image-size-next'}:
    raise SystemExit(f'ERRO: resolução inesperada para image-size: name={name!r} version={version!r}')
print(f'PASS image-size override -> name={name or "image-size-next"} version={version}')
PY

npm ls image-size image-size-next texture-compressor --all > ../outputs/full-project-gate/npm-image-size-tree.txt || true
cd "$ROOT"

git add maritime_ui/package.json maritime_ui/package-lock.json
if ! git diff --cached --quiet; then
  git commit -m "security: refresh maritime lockfile for image-size CVEs"
  git push origin HEAD:"$BRANCH"
fi

echo "MARITIME IMAGE-SIZE REMEDIATION: PASS"
