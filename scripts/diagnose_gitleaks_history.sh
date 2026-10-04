#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GITLEAKS_VERSION='8.30.1'
GITLEAKS_URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
GITLEAKS_SHA='551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
REPORT='/tmp/agrolog-gitleaks-history.json'

if [[ ! -x /tmp/gitleaks ]]; then
  curl --proto '=https' --tlsv1.2 -fsSLo /tmp/gitleaks.tar.gz "$GITLEAKS_URL"
  echo "${GITLEAKS_SHA}  /tmp/gitleaks.tar.gz" | sha256sum -c -
  tar -xzf /tmp/gitleaks.tar.gz -C /tmp gitleaks
fi

rm -f "$REPORT"
set +e
/tmp/gitleaks git --redact --no-banner --exit-code 1 \
  --report-format json --report-path "$REPORT" . >/tmp/agrolog-gitleaks-history.log 2>&1
code=$?
set -e

python - "$REPORT" <<'PY'
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

p = Path(sys.argv[1])
rows = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
print(f'GITLEAKS_HISTORY_FINDINGS={len(rows)}')
for idx, item in enumerate(rows, 1):
    commit = str(item.get('Commit') or '')
    path = str(item.get('File') or 'unknown')
    line = item.get('StartLine') or 'unknown'
    rule = str(item.get('RuleID') or 'unknown')
    description = str(item.get('Description') or '').replace('\n', ' ')[:120]
    subject = ''
    if commit:
        try:
            subject = subprocess.check_output(
                ['git', 'show', '-s', '--format=%s', commit],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()[:120]
        except Exception:
            subject = ''
    print(
        f'FINDING {idx}: rule={rule} file={path} line={line} '
        f'commit={commit[:12] or "unknown"} subject={subject!r} description={description!r}'
    )
print('SECRET_VALUES=REDACTED')
PY

if [[ "$code" -eq 0 ]]; then
  echo 'GITLEAKS_HISTORY_STATUS=PASS'
else
  echo "GITLEAKS_HISTORY_STATUS=BLOCKED exit=${code}"
fi
