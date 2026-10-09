#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for cmd in python git curl tar sha256sum npm node; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERRO: comando obrigatório ausente: $cmd" >&2; exit 2; }
done

mkdir -p outputs/full-project-gate

echo "===== 1/6 Dependências Python ====="
python - <<'PY'
from pathlib import Path
lines=[]
for path in sorted(Path('.').rglob('requirements*.txt')):
    if any(part in {'.git','.venv','venv'} for part in path.parts):
        continue
    for raw in path.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('-r ') or line.startswith('--requirement '):
            continue
        lines.append(line)
unique=list(dict.fromkeys(lines))
Path('/tmp/agrolog-requirements.txt').write_text('\n'.join(unique)+'\n', encoding='utf-8')
print(f'combined_requirements={len(unique)}')
PY
python -m pip install --disable-pip-version-check -r /tmp/agrolog-requirements.txt 'PyYAML>=6,<7'
python -m pip check

echo "===== 2/9 Bandit ====="
set +e
python -m bandit -q -r collector gateway models scripts ckan_connector socrata_connector cftc_cot usda_agtransport -ll -ii -f json -o outputs/full-project-gate/bandit.json
bandit_code=$?
set -e
python scripts/evaluate_bandit_report.py outputs/full-project-gate/bandit.json
if [[ "$bandit_code" -ne 0 ]]; then
  echo "Bandit reported findings; evaluator above is authoritative for Medium/High gate." >&2
fi

echo "===== 3/9 pip-audit ====="
python -m pip_audit -r /tmp/agrolog-requirements.txt

echo "===== 4/9 Zizmor ====="
zizmor --offline --persona=auditor --min-severity=high . | tee outputs/full-project-gate/zizmor.txt

echo "===== 5/9 actionlint ====="
ACTIONLINT_URL='https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz'
ACTIONLINT_SHA='8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8'
curl --proto '=https' --tlsv1.2 -fsSLo /tmp/actionlint.tar.gz "$ACTIONLINT_URL"
echo "${ACTIONLINT_SHA}  /tmp/actionlint.tar.gz" | sha256sum -c -
tar -xzf /tmp/actionlint.tar.gz -C /tmp actionlint
/tmp/actionlint

echo "===== 6/9 Gitleaks ====="
GITLEAKS_URL='https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz'
GITLEAKS_SHA='551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
curl --proto '=https' --tlsv1.2 -fsSLo /tmp/gitleaks.tar.gz "$GITLEAKS_URL"
echo "${GITLEAKS_SHA}  /tmp/gitleaks.tar.gz" | sha256sum -c -
tar -xzf /tmp/gitleaks.tar.gz -C /tmp gitleaks
set +e
/tmp/gitleaks dir --redact --no-banner --exit-code 1 --report-format json --report-path /tmp/gitleaks-report.json .
code=$?
set -e
if [[ "$code" -ne 0 ]]; then
  python - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/gitleaks-report.json')
rows=json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
for item in rows:
    print('GITLEAKS_FINDING', f"file={item.get('File','unknown')}", f"line={item.get('StartLine','unknown')}", f"rule={item.get('RuleID','unknown')}")
PY
  exit "$code"
fi
printf 'GITLEAKS TREE PASS\nversion=8.30.1\n' > outputs/full-project-gate/gitleaks.txt

echo "===== 7/9 Validador integral ====="
AGROLOG_EVIDENCE_GITLEAKS=outputs/full-project-gate/gitleaks.txt \
  python scripts/validate_full_project.py --mode ci --report outputs/full-project-gate/ci-report.json

echo "===== 8/9 npm audit ====="
(
  cd maritime_ui
  npm audit --omit=dev --audit-level=high
)

echo "===== 9/9 Resultado ====="
echo "AGROLOG MT LOCAL WHOLE-PROJECT CI: PASS"
echo "report=outputs/full-project-gate/ci-report.json"
