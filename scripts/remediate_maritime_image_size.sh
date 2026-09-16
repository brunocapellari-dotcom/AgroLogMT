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

package = json.loads(Path('package.json').read_text(encoding='utf-8'))
override = (package.get('overrides') or {}).get('image-size')
if override != 'npm:image-size-next@2.1.0':
    raise SystemExit(f'ERRO: override image-size inesperado: {override!r}')

lock = json.loads(Path('package-lock.json').read_text(encoding='utf-8'))
pkgs = lock.get('packages', {})
vulnerable = []
replacement = []
for path, entry in pkgs.items():
    version = str((entry or {}).get('version', ''))
    name = str((entry or {}).get('name', ''))
    resolved = str((entry or {}).get('resolved', ''))
    if path.endswith('node_modules/image-size') and version == '0.7.5':
        vulnerable.append(path)
    if 'image-size-0.7.5.tgz' in resolved:
        vulnerable.append(path or '<root>')
    if version == '2.1.0' and (name == 'image-size-next' or 'image-size-next' in resolved):
        replacement.append(path or '<root>')

if vulnerable:
    raise SystemExit('ERRO: image-size 0.7.5 vulnerável ainda presente: ' + ', '.join(sorted(set(vulnerable))))

image_entry = pkgs.get('node_modules/image-size')
if image_entry:
    version = str(image_entry.get('version', ''))
    name = str(image_entry.get('name', ''))
    resolved = str(image_entry.get('resolved', ''))
    if version != '2.1.0' or not (name in {'', 'image-size-next'} or 'image-size-next' in resolved):
        raise SystemExit(
            f'ERRO: resolução inesperada para node_modules/image-size: name={name!r} version={version!r} resolved={resolved!r}'
        )
    print(f'PASS image-size alias seguro instalado -> version={version}')
elif replacement:
    print('PASS image-size vulnerável removido; replacement seguro presente em ' + ', '.join(replacement))
else:
    # npm pode podar o peer opcional texture-compressor/image-size. Isto é seguro desde que
    # a versão vulnerável não exista no lockfile; o build acima prova que o bundle usado compila.
    print('PASS image-size vulnerável removido/podado; nenhuma cópia 0.7.5 no lockfile')
PY

npm ls image-size image-size-next texture-compressor --all > ../outputs/full-project-gate/npm-image-size-tree.txt || true
cd "$ROOT"

git add maritime_ui/package.json maritime_ui/package-lock.json
if ! git diff --cached --quiet; then
  git commit -m "security: refresh maritime lockfile for image-size CVEs"
  git push origin HEAD:"$BRANCH"
fi

echo "MARITIME IMAGE-SIZE REMEDIATION: PASS"
