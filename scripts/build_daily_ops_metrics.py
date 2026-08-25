from __future__ import annotations

import os
from google.cloud import bigquery


def main() -> int:
    project=os.getenv('AGROLOG_GCP_PROJECT') or os.getenv('GOOGLE_CLOUD_PROJECT')
    dataset=os.getenv('AGROLOG_OPS_DATASET','agrolog_ops')
    location=os.getenv('AGROLOG_BQ_LOCATION','southamerica-east1')
    if not project: raise SystemExit('AGROLOG_GCP_PROJECT ausente')
    client=bigquery.Client(project=project,location=location)
    fq=f'{project}.{dataset}'
    client.query(f"""
    CREATE TABLE IF NOT EXISTS `{fq}.daily_product_runs` (
      run_id STRING NOT NULL,
      product_id STRING NOT NULL,
      client_id STRING,
      started_at TIMESTAMP NOT NULL,
      finished_at TIMESTAMP,
      cutoff_at TIMESTAMP NOT NULL,
      status STRING NOT NULL,
      automated_steps INT64,
      manual_interventions INT64,
      manual_minutes FLOAT64,
      source_count INT64,
      source_lag_count INT64,
      source_error_count INT64,
      material_claim_count INT64,
      unsupported_claim_count INT64,
      correction_count INT64,
      false_positive_count INT64,
      false_negative_count INT64,
      compute_cost_estimated_brl NUMERIC,
      external_data_cost_brl NUMERIC,
      client_value_confirmed_brl NUMERIC,
      value_status STRING,
      model_versions_json STRING,
      notes STRING,
      inserted_at TIMESTAMP NOT NULL
    ) PARTITION BY DATE(started_at) CLUSTER BY product_id,status,client_id
    """).result()
    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_daily_product_kpis` AS
    SELECT
      product_id,
      COUNT(*) runs,
      COUNTIF(status='PASS')/COUNT(*) pass_rate,
      AVG(TIMESTAMP_DIFF(finished_at,started_at,SECOND)) avg_runtime_seconds,
      APPROX_QUANTILES(TIMESTAMP_DIFF(finished_at,started_at,SECOND),100 IGNORE NULLS)[OFFSET(95)] p95_runtime_seconds,
      AVG(manual_minutes) avg_manual_minutes,
      APPROX_QUANTILES(manual_minutes,100 IGNORE NULLS)[OFFSET(95)] p95_manual_minutes,
      SAFE_DIVIDE(SUM(source_lag_count),SUM(source_count)) source_lag_share,
      SAFE_DIVIDE(SUM(unsupported_claim_count),SUM(material_claim_count)) unsupported_claim_rate,
      SUM(correction_count) corrections,
      SUM(false_positive_count) false_positives,
      SUM(false_negative_count) false_negatives,
      SUM(compute_cost_estimated_brl+external_data_cost_brl) measured_or_estimated_cost_brl,
      SUM(client_value_confirmed_brl) client_confirmed_value_brl
    FROM `{fq}.daily_product_runs`
    GROUP BY product_id
    """).result()
    client.query(f"""
    CREATE OR REPLACE VIEW `{fq}.v_daily_operational_gate` AS
    SELECT
      product_id,
      runs,
      pass_rate,
      avg_manual_minutes,
      p95_manual_minutes,
      source_lag_share,
      unsupported_claim_rate,
      CASE
        WHEN runs < 10 THEN 'INSUFFICIENT_PRODUCTION_RUNS'
        WHEN pass_rate < 0.95 THEN 'HOLD_RELIABILITY'
        WHEN unsupported_claim_rate > 0 THEN 'HOLD_EVIDENCE'
        WHEN p95_manual_minutes > 180 THEN 'HOLD_MANUAL_EFFORT'
        ELSE 'OPERATING_BASELINE_PASS'
      END AS operating_gate
    FROM `{fq}.v_daily_product_kpis`
    """).result()
    print(f'Daily operational metrics ready in {fq}')
    return 0


if __name__=='__main__': raise SystemExit(main())
