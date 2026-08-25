from __future__ import annotations

import os

from google.cloud import bigquery


def main() -> int:
    project = os.environ.get("AGROLOG_GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    dataset = os.environ.get("AGROLOG_HIDRO_DATASET", "hidrologia")
    location = os.environ.get("AGROLOG_BQ_LOCATION", "southamerica-east1")
    if not project:
        raise SystemExit("AGROLOG_GCP_PROJECT/GOOGLE_CLOUD_PROJECT ausente")
    client = bigquery.Client(project=project, location=location)
    fq = f"{project}.{dataset}"

    statements = [
        f"""
        CREATE OR REPLACE VIEW `{fq}.hydro_station_daily` AS
        SELECT
          station_code,
          ANY_VALUE(station_name HAVING MAX data_hora_medicao) AS station_name,
          ANY_VALUE(river HAVING MAX data_hora_medicao) AS river,
          data_referencia,
          APPROX_QUANTILES(cota_cm, 100 IGNORE NULLS)[OFFSET(50)] AS stage_cm_median,
          MIN(cota_cm) AS stage_cm_min,
          MAX(cota_cm) AS stage_cm_max,
          APPROX_QUANTILES(vazao_m3s, 100 IGNORE NULLS)[OFFSET(50)] AS flow_m3s_median,
          SUM(IF(cota_status='0',1,0)) / COUNTIF(cota_cm IS NOT NULL) AS stage_qc_ok_share,
          SUM(IF(vazao_status='0',1,0)) / COUNTIF(vazao_m3s IS NOT NULL) AS flow_qc_ok_share,
          COUNT(*) AS readings,
          MAX(data_hora_medicao) AS latest_measurement,
          MAX(data_atualizacao) AS latest_source_update
        FROM `{fq}.hydro_station_telemetry`
        GROUP BY station_code, data_referencia
        """,
        f"""
        CREATE OR REPLACE VIEW `{fq}.hydro_climatology_doy` AS
        WITH base AS (
          SELECT
            station_code,
            EXTRACT(DAYOFYEAR FROM data_referencia) AS doy,
            EXTRACT(YEAR FROM data_referencia) AS yr,
            stage_cm_median,
            flow_m3s_median
          FROM `{fq}.hydro_station_daily`
          WHERE stage_cm_median IS NOT NULL OR flow_m3s_median IS NOT NULL
        ), targets AS (
          SELECT DISTINCT station_code, doy FROM base
        )
        SELECT
          t.station_code,
          t.doy,
          COUNT(DISTINCT b.yr) AS sample_years,
          COUNTIF(b.stage_cm_median IS NOT NULL) AS stage_samples,
          COUNTIF(b.flow_m3s_median IS NOT NULL) AS flow_samples,
          APPROX_QUANTILES(b.stage_cm_median,100 IGNORE NULLS)[OFFSET(1)] AS stage_p01,
          APPROX_QUANTILES(b.stage_cm_median,100 IGNORE NULLS)[OFFSET(5)] AS stage_p05,
          APPROX_QUANTILES(b.stage_cm_median,100 IGNORE NULLS)[OFFSET(10)] AS stage_p10,
          APPROX_QUANTILES(b.stage_cm_median,100 IGNORE NULLS)[OFFSET(25)] AS stage_p25,
          APPROX_QUANTILES(b.stage_cm_median,100 IGNORE NULLS)[OFFSET(50)] AS stage_p50,
          APPROX_QUANTILES(b.flow_m3s_median,100 IGNORE NULLS)[OFFSET(1)] AS flow_p01,
          APPROX_QUANTILES(b.flow_m3s_median,100 IGNORE NULLS)[OFFSET(5)] AS flow_p05,
          APPROX_QUANTILES(b.flow_m3s_median,100 IGNORE NULLS)[OFFSET(10)] AS flow_p10,
          APPROX_QUANTILES(b.flow_m3s_median,100 IGNORE NULLS)[OFFSET(25)] AS flow_p25,
          APPROX_QUANTILES(b.flow_m3s_median,100 IGNORE NULLS)[OFFSET(50)] AS flow_p50,
          IF(COUNT(DISTINCT b.yr)>=10,'SUFFICIENT','INSUFFICIENT_CLIMATOLOGY') AS climatology_quality
        FROM targets t
        JOIN base b
          ON b.station_code=t.station_code
         AND LEAST(ABS(b.doy-t.doy),366-ABS(b.doy-t.doy)) <= 15
        GROUP BY t.station_code,t.doy
        """,
        f"""
        CREATE OR REPLACE VIEW `{fq}.hydro_daily_trends` AS
        SELECT
          *,
          stage_cm_median - LAG(stage_cm_median,3) OVER(PARTITION BY station_code ORDER BY data_referencia) AS stage_delta_3obs,
          stage_cm_median - LAG(stage_cm_median,7) OVER(PARTITION BY station_code ORDER BY data_referencia) AS stage_delta_7obs,
          flow_m3s_median - LAG(flow_m3s_median,3) OVER(PARTITION BY station_code ORDER BY data_referencia) AS flow_delta_3obs,
          flow_m3s_median - LAG(flow_m3s_median,7) OVER(PARTITION BY station_code ORDER BY data_referencia) AS flow_delta_7obs
        FROM `{fq}.hydro_station_daily`
        """,
        f"""
        CREATE TABLE IF NOT EXISTS `{fq}.navigation_restrictions` (
          event_id STRING NOT NULL,
          river STRING NOT NULL,
          segment STRING,
          data_referencia DATE NOT NULL,
          data_publicacao TIMESTAMP,
          data_coleta TIMESTAMP NOT NULL,
          restriction_type STRING NOT NULL,
          severity STRING,
          draft_m FLOAT64,
          load_reduction_pct FLOAT64,
          interruption_flag BOOL,
          observed_flag BOOL NOT NULL,
          source_org STRING NOT NULL,
          source_url STRING NOT NULL,
          evidence_id STRING,
          notes STRING
        )
        PARTITION BY data_referencia
        CLUSTER BY river, restriction_type, severity
        """,
        f"""
        CREATE OR REPLACE VIEW `{fq}.m04_components_latest` AS
        WITH ranked AS (
          SELECT d.*, ROW_NUMBER() OVER(PARTITION BY station_code ORDER BY data_referencia DESC) rn
          FROM `{fq}.hydro_daily_trends` d
        ), current AS (
          SELECT * FROM ranked WHERE rn=1
        ), joined AS (
          SELECT
            c.*,
            cl.sample_years,cl.climatology_quality,
            cl.stage_p01,cl.stage_p05,cl.stage_p10,cl.stage_p25,cl.stage_p50,
            CASE
              WHEN cl.climatology_quality!='SUFFICIENT' OR c.stage_cm_median IS NULL THEN NULL
              WHEN c.stage_cm_median >= cl.stage_p25 THEN 0
              WHEN c.stage_cm_median >= cl.stage_p10 THEN 25
              WHEN c.stage_cm_median >= cl.stage_p05 THEN 50
              WHEN c.stage_cm_median >= cl.stage_p01 THEN 75
              ELSE 100
            END AS h_score
          FROM current c
          LEFT JOIN `{fq}.hydro_climatology_doy` cl
            ON cl.station_code=c.station_code
           AND cl.doy=EXTRACT(DAYOFYEAR FROM c.data_referencia)
        )
        SELECT
          j.*,
          (SELECT MAX(CASE severity WHEN 'CRITICAL' THEN 100 WHEN 'HIGH' THEN 80 WHEN 'ELEVATED' THEN 60 WHEN 'ATTENTION' THEN 25 ELSE 0 END)
           FROM `{fq}.navigation_restrictions` r
           WHERE LOWER(r.river)=LOWER(j.river)
             AND r.observed_flag
             AND r.data_referencia >= DATE_SUB(j.data_referencia, INTERVAL 7 DAY)) AS o_score,
          'T_SCORE_PENDING_HISTORICAL_SLOPE_CALIBRATION' AS t_gate,
          'P_SCORE_PENDING_BASIN_PRECIP' AS p_gate,
          'F_SCORE_PENDING_POINT_IN_TIME_FORECAST' AS f_gate
        FROM joined j
        """,
    ]
    for statement in statements:
        client.query(statement).result()
    print(f"M04 views/tables updated in {fq}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
