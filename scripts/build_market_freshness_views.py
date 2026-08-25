from __future__ import annotations

import os

from google.cloud import bigquery


def main() -> int:
    project = os.getenv("AGROLOG_GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    dataset = os.getenv("AGROLOG_MERCADO_DATASET", "mercado")
    location = os.getenv("AGROLOG_BQ_LOCATION", "southamerica-east1")
    if not project:
        raise SystemExit("AGROLOG_GCP_PROJECT ausente")
    client = bigquery.Client(project=project, location=location)
    fq = f"{project}.{dataset}"

    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_ptax_publication_latency` AS
    SELECT
      data_referencia,
      data_hora_cotacao,
      data_coleta,
      TIMESTAMP_DIFF(data_coleta, data_hora_cotacao, MINUTE) AS collection_lag_minutes,
      cotacao_compra,
      cotacao_venda,
      source_url,
      snapshot_sha256,
      CASE
        WHEN TIMESTAMP_DIFF(data_coleta, data_hora_cotacao, MINUTE) <= 360 THEN 'SLA_GREEN'
        WHEN TIMESTAMP_DIFF(data_coleta, data_hora_cotacao, MINUTE) <= 1440 THEN 'SLA_YELLOW'
        ELSE 'SLA_RED'
      END AS collection_sla
    FROM `{fq}.ptax_usd_daily`
    """).result()

    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_ptax_freshness` AS
    WITH latest AS (
      SELECT * FROM `{fq}.ptax_usd_daily`
      QUALIFY ROW_NUMBER() OVER(ORDER BY data_hora_cotacao DESC, data_coleta DESC)=1
    )
    SELECT
      *,
      DATE_DIFF(CURRENT_DATE('America/Cuiaba'), data_referencia, DAY) AS reference_age_days,
      TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), data_coleta, HOUR) AS collection_age_hours,
      CASE
        WHEN DATE_DIFF(CURRENT_DATE('America/Cuiaba'), data_referencia, DAY) <= 1 THEN 'FRESH'
        WHEN DATE_DIFF(CURRENT_DATE('America/Cuiaba'), data_referencia, DAY) <= 4 THEN 'SOURCE_LAG_OR_NON_BUSINESS_DAY'
        ELSE 'STALE'
      END AS freshness_status
    FROM latest
    """).result()

    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_ptax_sla_monthly` AS
    SELECT
      FORMAT_DATE('%Y-%m', data_referencia) AS competencia,
      COUNT(*) AS observations,
      APPROX_QUANTILES(collection_lag_minutes,100)[OFFSET(50)] AS p50_collection_lag_min,
      APPROX_QUANTILES(collection_lag_minutes,100)[OFFSET(95)] AS p95_collection_lag_min,
      COUNTIF(collection_sla='SLA_GREEN')/COUNT(*) AS green_share
    FROM `{fq}.v_ptax_publication_latency`
    GROUP BY competencia
    """).result()
    print(f"PTAX freshness views built in {fq}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
