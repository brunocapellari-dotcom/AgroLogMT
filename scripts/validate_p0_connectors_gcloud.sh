#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-southamerica-east1}"
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
MERCADO_DATASET="${MERCADO_DATASET:-mercado}"
HIDRO_DATASET="${HIDRO_DATASET:-hidrologia}"
EVIDENCE_DIR="${EVIDENCE_DIR:-outputs/p0-connectors}"
JOB="${JOB:-agrolog-p0}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Projeto GCP ausente" >&2
  exit 2
fi

mkdir -p "${EVIDENCE_DIR}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${EVIDENCE_DIR}/${TS}"
mkdir -p "${OUT}"

bq query --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" --use_legacy_sql=false --format=prettyjson \
"SELECT data_referencia,cotacao_compra,cotacao_venda,data_hora_cotacao,source_url,snapshot_sha256
 FROM \`${PROJECT_ID}.${MERCADO_DATASET}.ptax_usd_daily\`
 ORDER BY data_hora_cotacao DESC LIMIT 10" > "${OUT}/ptax_latest.json"

bq query --project_id="${PROJECT_ID}" --location="${BQ_LOCATION}" --use_legacy_sql=false --format=prettyjson \
"SELECT station_code,ANY_VALUE(station_name) station_name,ANY_VALUE(river) river,
        COUNT(*) records,MAX(data_hora_medicao) latest_measurement,
        COUNTIF(cota_status='0') cota_qc_ok,COUNTIF(vazao_status='0') vazao_qc_ok
 FROM \`${PROJECT_ID}.${HIDRO_DATASET}.hydro_station_telemetry\`
 WHERE data_referencia >= DATE_SUB(CURRENT_DATE('America/Cuiaba'), INTERVAL 35 DAY)
 GROUP BY station_code ORDER BY station_code" > "${OUT}/ana_station_coverage.json"

python - "${OUT}/ptax_latest.json" "${OUT}/ana_station_coverage.json" <<'PY'
import json,sys
from datetime import date, datetime
ptax=json.load(open(sys.argv[1],encoding='utf-8'))
hydro=json.load(open(sys.argv[2],encoding='utf-8'))
if not ptax:
    raise SystemExit('PTAX_EMPTY')
latest=date.fromisoformat(str(ptax[0]['data_referencia'])[:10])
age=(date.today()-latest).days
if age > 4:
    raise SystemExit(f'PTAX_STALE_{age}D')
expected={'15400000','15320002','15630000','17730000','17900000'}
got={str(row['station_code']) for row in hydro if int(row.get('records',0) or 0)>0}
missing=sorted(expected-got)
if missing:
    raise SystemExit('ANA_STATIONS_MISSING:'+','.join(missing))
print(json.dumps({'ptax_latest':latest.isoformat(),'ptax_age_days':age,'ana_stations':sorted(got),'status':'DATA_GATE_PASS'},ensure_ascii=False))
PY

# Log safety: nenhum nome de segredo/token de autenticação deve aparecer no output do job.
gcloud logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=${JOB}" \
  --project "${PROJECT_ID}" --freshness=24h --limit=1000 --format=json > "${OUT}/job_logs.json" || true

if grep -Eqi 'tokenautenticacao|ANA_SENHA|ANA_IDENTIFICADOR|Authorization[^\n]*Bearer' "${OUT}/job_logs.json"; then
  echo "SECRET_LOG_PATTERN_DETECTED" >&2
  exit 5
fi

cat > "${OUT}/RESULT.txt" <<EOF
P0 CONNECTORS: PASS
project=${PROJECT_ID}
region=${REGION}
ptax=${PROJECT_ID}.${MERCADO_DATASET}.ptax_usd_daily
hydro=${PROJECT_ID}.${HIDRO_DATASET}.hydro_station_telemetry
evidence_dir=${OUT}
secret_log_pattern=PASS
EOF

cat "${OUT}/RESULT.txt"
