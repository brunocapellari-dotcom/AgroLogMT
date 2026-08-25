from __future__ import annotations

import os
from google.cloud import bigquery


def main() -> int:
    project = os.getenv('AGROLOG_GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
    dataset = os.getenv('AGROLOG_MERCADO_DATASET','mercado')
    location = os.getenv('AGROLOG_BQ_LOCATION','southamerica-east1')
    if not project:
        raise SystemExit('AGROLOG_GCP_PROJECT ausente')
    client = bigquery.Client(project=project, location=location)
    fq=f'{project}.{dataset}'

    client.query(f"""
    CREATE TABLE IF NOT EXISTS `{fq}.mdic_trade_vintages` (
      vintage_id STRING NOT NULL,
      release_type STRING NOT NULL,
      flow STRING,
      product_key STRING,
      geography_key STRING,
      period_start DATE NOT NULL,
      period_end DATE NOT NULL,
      data_publicacao TIMESTAMP NOT NULL,
      data_coleta TIMESTAMP NOT NULL,
      value_usd_fob NUMERIC,
      quantity_kg NUMERIC,
      netweight_kg NUMERIC,
      source_url STRING NOT NULL,
      source_hash STRING,
      evidence_class STRING NOT NULL,
      status STRING NOT NULL,
      notes STRING
    )
    PARTITION BY period_end
    CLUSTER BY release_type, flow, product_key, geography_key
    """).result()

    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_mdic_revision_tracker` AS
    WITH weekly AS (
      SELECT * FROM `{fq}.mdic_trade_vintages`
      WHERE release_type='WEEKLY_PRELIMINARY' AND status='MATERIALIZED'
    ), monthly AS (
      SELECT * FROM `{fq}.mdic_trade_vintages`
      WHERE release_type='MONTHLY_CONSOLIDATED' AND status='MATERIALIZED'
    )
    SELECT
      w.flow,w.product_key,w.geography_key,
      w.period_start,w.period_end,
      w.vintage_id AS weekly_vintage_id,
      w.data_publicacao AS weekly_publication,
      m.vintage_id AS monthly_vintage_id,
      m.data_publicacao AS monthly_publication,
      w.value_usd_fob AS weekly_value_usd_fob,
      m.value_usd_fob AS monthly_value_usd_fob,
      SAFE_DIVIDE(m.value_usd_fob-w.value_usd_fob,NULLIF(w.value_usd_fob,0))*100 AS value_revision_pct,
      w.netweight_kg AS weekly_netweight_kg,
      m.netweight_kg AS monthly_netweight_kg,
      SAFE_DIVIDE(m.netweight_kg-w.netweight_kg,NULLIF(w.netweight_kg,0))*100 AS netweight_revision_pct,
      CASE WHEN m.vintage_id IS NULL THEN 'AWAITING_MONTHLY_CONSOLIDATION' ELSE 'COMPARABLE' END AS comparison_status
    FROM weekly w
    LEFT JOIN monthly m
      ON m.flow=w.flow
     AND COALESCE(m.product_key,'')=COALESCE(w.product_key,'')
     AND COALESCE(m.geography_key,'')=COALESCE(w.geography_key,'')
     AND EXTRACT(YEAR FROM m.period_end)=EXTRACT(YEAR FROM w.period_end)
     AND EXTRACT(MONTH FROM m.period_end)=EXTRACT(MONTH FROM w.period_end)
    """).result()

    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_mdic_revision_risk` AS
    SELECT
      product_key,geography_key,
      COUNTIF(comparison_status='COMPARABLE') AS comparable_vintages,
      APPROX_QUANTILES(ABS(value_revision_pct),100 IGNORE NULLS)[OFFSET(50)] AS median_abs_value_revision_pct,
      APPROX_QUANTILES(ABS(value_revision_pct),100 IGNORE NULLS)[OFFSET(95)] AS p95_abs_value_revision_pct,
      APPROX_QUANTILES(ABS(netweight_revision_pct),100 IGNORE NULLS)[OFFSET(50)] AS median_abs_netweight_revision_pct,
      CASE
        WHEN COUNTIF(comparison_status='COMPARABLE') < 6 THEN 'INSUFFICIENT_HISTORY'
        WHEN APPROX_QUANTILES(ABS(value_revision_pct),100 IGNORE NULLS)[OFFSET(95)] <= 2 THEN 'LOW'
        WHEN APPROX_QUANTILES(ABS(value_revision_pct),100 IGNORE NULLS)[OFFSET(95)] <= 5 THEN 'MODERATE'
        ELSE 'HIGH'
      END AS revision_risk
    FROM `{fq}.v_mdic_revision_tracker`
    GROUP BY product_key,geography_key
    """).result()
    print(f'MDIC revision tracker built in {fq}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
