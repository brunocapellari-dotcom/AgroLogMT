#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${PROJECT_ID:-${AGROLOG_GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
OUT="${OUT:-outputs/agrolog360-homologation}"

[[ -n "$PROJECT_ID" && "$PROJECT_ID" != "(unset)" ]] || { echo "ERRO: PROJECT_ID ausente" >&2; exit 2; }
mkdir -p "$OUT"

echo "===== 1/5 Source readiness ====="
python scripts/agrolog360_readiness.py --out "$OUT/source-readiness.json"

echo "===== 2/5 Mart plan ====="
python scripts/plan_agrolog360_marts.py --project "$PROJECT_ID" --out-dir "$OUT/marts"

echo "===== 3/5 Apply dependency-ready marts ====="
python scripts/apply_agrolog360_marts.py   --project "$PROJECT_ID"   --location "$BQ_LOCATION"   --execute   --out "$OUT/marts-apply.json"

echo "===== 4/5 Gateway ====="
python scripts/validate_agrolog360_gateway.py   --project "$PROJECT_ID"   --out "$OUT/gateway.json"

echo "===== 5/5 Seal ====="
python - "$OUT" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
sources = json.loads((out / "source-readiness.json").read_text())
marts = json.loads((out / "marts-apply.json").read_text())
gateway = json.loads((out / "gateway.json").read_text())

applied = [row for row in marts["marts"] if row["status"] == "APPLIED"]
gated = [row for row in marts["marts"] if row["status"] == "GATED"]
status = "PASS" if gateway["status"] == "PASS" and applied and not any(
    row["mart_id"] in {"climate_rollups", "storage_balance", "overview_current"} for row in gated
) else "BLOCKED"

report = {
    "status": status,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source_readiness": {
        key: sources[key] for key in ("priority_sources", "active", "gated", "planned")
    },
    "marts_applied": [row["mart_id"] for row in applied],
    "marts_gated": gated,
    "gateway_status": gateway["status"],
}
(out / "RESULT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2))
if status != "PASS":
    raise SystemExit(2)
print("AGROLOG 360 OPERATIONAL HOMOLOGATION: PASS")
PY
