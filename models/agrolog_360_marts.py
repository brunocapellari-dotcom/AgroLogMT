from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _safe(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid identifier: {value!r}")
    return value


def _q(project_id: str, dataset: str, table: str) -> str:
    return f"`{_safe(project_id)}.{_safe(dataset)}.{_safe(table)}`"


@dataclass(frozen=True)
class MartSql:
    mart_id: str
    target: str
    sql: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def climate_rollups_sql(project_id: str) -> MartSql:
    source = _q(project_id, "clima", "daily_observations")
    target_name = "marts_agrolog360.climate_rollups_v1"
    target = _q(project_id, "marts_agrolog360", "climate_rollups_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  source_id, geo_id, data_referencia,
  precipitacao_mm,
  SUM(precipitacao_mm) OVER (PARTITION BY source_id, geo_id ORDER BY data_referencia ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS chuva_7d_mm,
  SUM(precipitacao_mm) OVER (PARTITION BY source_id, geo_id ORDER BY data_referencia ROWS BETWEEN 14 PRECEDING AND CURRENT ROW) AS chuva_15d_mm,
  SUM(precipitacao_mm) OVER (PARTITION BY source_id, geo_id ORDER BY data_referencia ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS chuva_30d_mm,
  SUM(precipitacao_mm) OVER (PARTITION BY source_id, geo_id ORDER BY data_referencia ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS chuva_60d_mm,
  SUM(precipitacao_mm) OVER (PARTITION BY source_id, geo_id ORDER BY data_referencia ROWS BETWEEN 89 PRECEDING AND CURRENT ROW) AS chuva_90d_mm,
  tmin_c, tmax_c, data_publicacao, data_coleta, competencia, evidence_class
FROM {source}
""".strip()
    return MartSql("climate_rollups", target_name, sql)


def storage_balance_sql(project_id: str) -> MartSql:
    production = _q(project_id, "agro", "conab_safra_graos")
    storage = _q(project_id, "logistica", "v_armazens_conab_latest")
    target_name = "marts_agrolog360.storage_balance_v1"
    target = _q(project_id, "marts_agrolog360", "storage_balance_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
WITH p AS (
  SELECT geo_id AS uf, safra, SUM(producao_mil_t) * 1000 AS producao_t,
         MAX(data_publicacao) AS data_publicacao, MAX(data_coleta) AS data_coleta,
         STRING_AGG(DISTINCT evidence_class, ',' ORDER BY evidence_class) AS source_evidence_classes
  FROM {production}
  WHERE geo_level='UF'
  GROUP BY uf, safra
),
s AS (
  SELECT uf, SUM(COALESCE(capacidade_estatica_t,0)) AS capacidade_estatica_t
  FROM {storage}
  GROUP BY uf
)
SELECT
  p.uf, p.safra, p.producao_t, s.capacidade_estatica_t,
  SAFE_DIVIDE(p.producao_t, s.capacidade_estatica_t) AS producao_capacidade_ratio,
  s.capacidade_estatica_t - p.producao_t AS gap_capacidade_t,
  p.data_publicacao, p.data_coleta,
  p.source_evidence_classes,
  'INFERIDO' AS evidence_class
FROM p
LEFT JOIN s USING (uf)
""".strip()
    return MartSql("storage_balance", target_name, sql)


def freight_lanes_sql(project_id: str) -> MartSql:
    source = _q(project_id, "logistica", "freight_offer_observations")
    target_name = "marts_agrolog360.freight_lanes_v1"
    target = _q(project_id, "marts_agrolog360", "freight_lanes_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  origin_municipality_id, destination_municipality_id, product_id,
  DATE(data_referencia) AS data_referencia,
  COUNT(*) AS raw_offer_count,
  COUNT(DISTINCT dedup_cluster_id) AS unique_offer_clusters,
  APPROX_QUANTILES(freight_brl_per_t, 100)[OFFSET(50)] AS freight_brl_per_t_p50,
  APPROX_QUANTILES(freight_brl_per_t_km, 100)[OFFSET(50)] AS freight_brl_per_t_km_p50,
  MAX(data_coleta) AS data_coleta,
  'DERIVADO_DE_OFERTAS_OBSERVADAS' AS evidence_class
FROM {source}
WHERE requires_review=FALSE
GROUP BY origin_municipality_id, destination_municipality_id, product_id, data_referencia
""".strip()
    return MartSql("freight_lanes", target_name, sql)


def fertilizer_trade_sql(project_id: str) -> MartSql:
    source = _q(project_id, "comercio_exterior", "comexstat_ncm_import")
    target_name = "marts_agrolog360.fertilizer_imports_v1"
    target = _q(project_id, "marts_agrolog360", "fertilizer_imports_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  competencia, co_ncm, co_pais, sg_uf_ncm, co_via, co_urf,
  SUM(toneladas) AS toneladas,
  SUM(vl_fob) AS vl_fob,
  SAFE_DIVIDE(SUM(vl_fob), NULLIF(SUM(toneladas),0)) AS usd_por_t,
  MAX(data_publicacao) AS data_publicacao,
  MAX(data_coleta) AS data_coleta,
  'OBSERVADO_COMEXSTAT' AS evidence_class
FROM {source}
WHERE STARTS_WITH(co_ncm, '31')
GROUP BY competencia, co_ncm, co_pais, sg_uf_ncm, co_via, co_urf
""".strip()
    return MartSql("fertilizer_imports", target_name, sql)


def biomass_sql(project_id: str) -> MartSql:
    source = _q(project_id, "energia", "biomass_observations")
    target_name = "marts_agrolog360.biomass_v1"
    target = _q(project_id, "marts_agrolog360", "biomass_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  source_id, geo_id, biomass_type, metric_id, value, unit,
  data_referencia, data_publicacao, data_coleta, competencia,
  evidence_class, observation_semantics, source_quality, quality_flags
FROM {source}
""".strip()
    return MartSql("biomass", target_name, sql)



def hydrology_latest_sql(project_id: str) -> MartSql:
    source = _q(project_id, "hidrologia", "m04_components_latest")
    target_name = "marts_agrolog360.hydrology_latest_v1"
    target = _q(project_id, "marts_agrolog360", "hydrology_latest_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  station_code, station_name, river, data_referencia,
  stage_cm_median, flow_m3s_median,
  stage_delta_3obs, stage_delta_7obs,
  flow_delta_3obs, flow_delta_7obs,
  sample_years, climatology_quality,
  h_score, o_score, t_gate, p_gate, f_gate,
  latest_measurement, latest_source_update,
  'DERIVADO_DE_OBSERVADO' AS evidence_class
FROM {source}
""".strip()
    return MartSql("hydrology_latest", target_name, sql)


def ptax_current_sql(project_id: str) -> MartSql:
    source = _q(project_id, "mercado", "ptax_usd_daily")
    target_name = "marts_agrolog360.ptax_current_v1"
    target = _q(project_id, "marts_agrolog360", "ptax_current_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT * EXCEPT(rn)
FROM (
  SELECT
    data_referencia, data_publicacao, data_coleta, competencia,
    moeda, cotacao_compra, cotacao_venda, data_hora_cotacao,
    source_url, snapshot_sha256, evidence_class, collector_version,
    ROW_NUMBER() OVER (
      PARTITION BY moeda
      ORDER BY data_referencia DESC, data_hora_cotacao DESC, data_coleta DESC
    ) AS rn
  FROM {source}
)
WHERE rn=1
""".strip()
    return MartSql("ptax_current", target_name, sql)


def imea_freight_reference_sql(project_id: str) -> MartSql:
    source = _q(project_id, "logistica", "imea_frete_referencia")
    target_name = "marts_agrolog360.imea_freight_reference_v1"
    target = _q(project_id, "marts_agrolog360", "imea_freight_reference_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  snapshot_id, record_id, data_referencia, produto, metric_name,
  origem, destino, valor, unidade_origem, unidade_canonica,
  evidence_class, evidence_subtype, negotiated,
  data_coleta, source_hash,
  'UNCLASSIFIED' AS route_type
FROM {source}
""".strip()
    return MartSql("imea_freight_reference", target_name, sql)

def overview_sql(project_id: str) -> MartSql:
    storage = _q(project_id, "marts_agrolog360", "storage_balance_v1")
    climate = _q(project_id, "marts_agrolog360", "climate_rollups_v1")
    target_name = "marts_agrolog360.overview_current_v1"
    target = _q(project_id, "marts_agrolog360", "overview_current_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
WITH latest_storage AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY uf ORDER BY safra DESC, data_coleta DESC) rn
    FROM {storage}
  ) WHERE rn=1
),
latest_climate AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY geo_id ORDER BY data_referencia DESC, data_coleta DESC) rn
    FROM {climate}
  ) WHERE rn=1
)
SELECT
  s.uf,
  s.safra,
  s.producao_t,
  s.capacidade_estatica_t,
  s.producao_capacidade_ratio,
  s.gap_capacidade_t,
  c.chuva_7d_mm,
  c.chuva_30d_mm,
  c.chuva_90d_mm,
  GREATEST(s.data_coleta, COALESCE(c.data_coleta, s.data_coleta)) AS data_coleta
FROM latest_storage s
LEFT JOIN latest_climate c ON c.geo_id=s.uf
""".strip()
    return MartSql("overview_current", target_name, sql)


def crop_vintages_sql(project_id: str) -> MartSql:
    source = _q(project_id, "agro", "conab_safra_graos")
    target_name = "marts_agrolog360.crop_vintages_v1"
    target = _q(project_id, "marts_agrolog360", "crop_vintages_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
WITH ordered AS (
  SELECT
    snapshot_id, source_id, geo_level, geo_id, product_id, safra, vintage_position,
    area_mil_ha, produtividade_kg_ha, producao_mil_t,
    data_referencia, data_publicacao, data_coleta, competencia,
    evidence_class, raw_artifact_ref, source_url, source_hash, source_sheet, source_row,
    LAG(area_mil_ha) OVER w AS previous_area_mil_ha,
    LAG(produtividade_kg_ha) OVER w AS previous_produtividade_kg_ha,
    LAG(producao_mil_t) OVER w AS previous_producao_mil_t
  FROM {source}
  WINDOW w AS (
    PARTITION BY geo_level, geo_id, product_id, safra, vintage_position
    ORDER BY data_publicacao, data_coleta, snapshot_id
  )
)
SELECT *,
  area_mil_ha - previous_area_mil_ha AS delta_area_mil_ha,
  SAFE_MULTIPLY(SAFE_DIVIDE(area_mil_ha - previous_area_mil_ha, NULLIF(ABS(previous_area_mil_ha),0)),100) AS delta_area_pct,
  produtividade_kg_ha - previous_produtividade_kg_ha AS delta_produtividade_kg_ha,
  SAFE_MULTIPLY(SAFE_DIVIDE(produtividade_kg_ha - previous_produtividade_kg_ha, NULLIF(ABS(previous_produtividade_kg_ha),0)),100) AS delta_produtividade_pct,
  producao_mil_t - previous_producao_mil_t AS delta_producao_mil_t,
  SAFE_MULTIPLY(SAFE_DIVIDE(producao_mil_t - previous_producao_mil_t, NULLIF(ABS(previous_producao_mil_t),0)),100) AS delta_producao_pct
FROM ordered
""".strip()
    return MartSql("crop_vintages", target_name, sql)


def crop_current_sql(project_id: str) -> MartSql:
    source = _q(project_id, "marts_agrolog360", "crop_vintages_v1")
    target_name = "marts_agrolog360.crop_current_v1"
    target = _q(project_id, "marts_agrolog360", "crop_current_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT * EXCEPT(rn)
FROM (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY geo_level, geo_id, product_id, safra, vintage_position
      ORDER BY data_publicacao DESC, data_coleta DESC, snapshot_id DESC
    ) AS rn
  FROM {source}
)
WHERE rn=1
""".strip()
    return MartSql("crop_current", target_name, sql)


def freight_history_sql(project_id: str) -> MartSql:
    source = _q(project_id, "marts_agrolog360", "freight_lanes_v1")
    target_name = "marts_agrolog360.freight_history_v1"
    target = _q(project_id, "marts_agrolog360", "freight_history_v1")
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  *,
  LAG(freight_brl_per_t_p50) OVER lane AS freight_brl_per_t_previous,
  AVG(freight_brl_per_t_p50) OVER (
    PARTITION BY origin_municipality_id, destination_municipality_id, product_id
    ORDER BY UNIX_DATE(data_referencia) RANGE BETWEEN 6 PRECEDING AND CURRENT ROW
  ) AS freight_brl_per_t_avg_7d,
  AVG(freight_brl_per_t_p50) OVER (
    PARTITION BY origin_municipality_id, destination_municipality_id, product_id
    ORDER BY UNIX_DATE(data_referencia) RANGE BETWEEN 29 PRECEDING AND CURRENT ROW
  ) AS freight_brl_per_t_avg_30d,
  PERCENT_RANK() OVER (
    PARTITION BY origin_municipality_id, destination_municipality_id, product_id
    ORDER BY freight_brl_per_t_p50
  ) * 100 AS historical_percentile
FROM {source}
WINDOW lane AS (
  PARTITION BY origin_municipality_id, destination_municipality_id, product_id
  ORDER BY data_referencia
)
""".strip()
    return MartSql("freight_history", target_name, sql)


def build_agrolog360_sql_bundle(project_id: str) -> tuple[MartSql, ...]:
    return (
        climate_rollups_sql(project_id),
        storage_balance_sql(project_id),
        freight_lanes_sql(project_id),
        fertilizer_trade_sql(project_id),
        biomass_sql(project_id),
        hydrology_latest_sql(project_id),
        ptax_current_sql(project_id),
        imea_freight_reference_sql(project_id),
        overview_sql(project_id),
        crop_vintages_sql(project_id),
        crop_current_sql(project_id),
        freight_history_sql(project_id),
    )
