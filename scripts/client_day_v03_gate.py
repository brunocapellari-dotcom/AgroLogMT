from __future__ import annotations

import json
import os
from datetime import date

from google.cloud import bigquery

EXPECTED_STATIONS={'15400000','15320002','15630000','17730000','17900000'}


def _count(client, sql):
    rows=list(client.query(sql).result())
    return int(rows[0][0]) if rows else 0


def main() -> int:
    project=os.getenv('AGROLOG_GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
    location=os.getenv('AGROLOG_BQ_LOCATION','southamerica-east1')
    mercado=os.getenv('AGROLOG_MERCADO_DATASET','mercado')
    hidro=os.getenv('AGROLOG_HIDRO_DATASET','hidrologia')
    if not project: raise SystemExit('AGROLOG_GCP_PROJECT ausente')
    client=bigquery.Client(project=project,location=location)
    result={'gate':'CLIENT_DAY_ZERO_P0_GAPS','checks':{}}

    ptax=list(client.query(f"SELECT data_referencia FROM `{project}.{mercado}.ptax_usd_daily` ORDER BY data_hora_cotacao DESC LIMIT 1").result())
    latest_ptax=str(ptax[0]['data_referencia']) if ptax else None
    ptax_age=(date.today()-date.fromisoformat(latest_ptax)).days if latest_ptax else None
    result['checks']['ptax']={'latest':latest_ptax,'age_days':ptax_age,'pass':ptax_age is not None and ptax_age<=4}

    hydro_rows=list(client.query(f"""
      SELECT station_code,MAX(data_hora_medicao) latest
      FROM `{project}.{hidro}.hydro_station_telemetry`
      WHERE data_referencia>=DATE_SUB(CURRENT_DATE('America/Cuiaba'),INTERVAL 35 DAY)
      GROUP BY station_code
    """).result())
    got={str(r['station_code']) for r in hydro_rows if r['latest'] is not None}
    result['checks']['ana']={'stations':sorted(got),'missing':sorted(EXPECTED_STATIONS-got),'pass':EXPECTED_STATIONS<=got}

    # Weekly MDIC is event-driven: a release can only pass if a materialized weekly vintage exists for the latest confirmed release period.
    try:
        mdic=_count(client,f"SELECT COUNT(*) FROM `{project}.{mercado}.mdic_trade_vintages` WHERE release_type='WEEKLY_PRELIMINARY' AND status='MATERIALIZED' AND period_end>=DATE_SUB(CURRENT_DATE('America/Cuiaba'),INTERVAL 14 DAY)")
    except Exception:
        mdic=0
    result['checks']['mdic_weekly']={'recent_materialized_vintages':mdic,'pass':mdic>0}

    passed=all(x['pass'] for x in result['checks'].values())
    result['status']='PASS' if passed else 'HOLD_P0'
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0 if passed else 3


if __name__=='__main__': raise SystemExit(main())
