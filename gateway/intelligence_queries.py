from __future__ import annotations

from .storage_queries import safe_identifier


def build_overview_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  uf, safra, producao_t, capacidade_estatica_t,
  producao_capacidade_ratio, gap_capacidade_t,
  chuva_7d_mm, chuva_30d_mm, chuva_90d_mm,
  data_coleta
FROM `{project}.{dataset}.overview_current_v1`
WHERE (@uf IS NULL OR uf=@uf)
ORDER BY data_coleta DESC
LIMIT 1
""".strip()


def build_storage_balance_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  uf, safra, producao_t, capacidade_estatica_t,
  producao_capacidade_ratio, gap_capacidade_t,
  data_publicacao, data_coleta, evidence_class
FROM `{project}.{dataset}.storage_balance_v1`
WHERE (@uf IS NULL OR uf=@uf)
ORDER BY safra DESC, data_coleta DESC
LIMIT @limit
""".strip()


def build_freight_lanes_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  origin_municipality_id, destination_municipality_id, product_id,
  data_referencia, raw_offer_count, unique_offer_clusters,
  freight_brl_per_t_p50, freight_brl_per_t_km_p50,
  data_coleta, evidence_class
FROM `{project}.{dataset}.freight_lanes_v1`
WHERE (@origin IS NULL OR origin_municipality_id=@origin)
  AND (@destination IS NULL OR destination_municipality_id=@destination)
  AND (@product IS NULL OR product_id=@product)
ORDER BY data_referencia DESC, unique_offer_clusters DESC
LIMIT @limit
""".strip()


def build_fertilizer_imports_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  competencia, co_ncm, co_pais, sg_uf_ncm, co_via, co_urf,
  toneladas, vl_fob, usd_por_t, data_publicacao, data_coleta, evidence_class
FROM `{project}.{dataset}.fertilizer_imports_v1`
WHERE (@uf IS NULL OR sg_uf_ncm=@uf)
ORDER BY competencia DESC, toneladas DESC
LIMIT @limit
""".strip()


def build_biomass_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  source_id, geo_id, biomass_type, metric_id, value, unit,
  data_referencia, data_publicacao, data_coleta, competencia,
  evidence_class, observation_semantics, source_quality, quality_flags
FROM `{project}.{dataset}.biomass_v1`
WHERE (@geo_id IS NULL OR geo_id=@geo_id)
  AND (@biomass_type IS NULL OR biomass_type=@biomass_type)
ORDER BY data_referencia DESC, source_id
LIMIT @limit
""".strip()


def build_hydrology_latest_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  station_code, station_name, river, data_referencia,
  stage_cm_median, flow_m3s_median,
  stage_delta_3obs, stage_delta_7obs,
  flow_delta_3obs, flow_delta_7obs,
  sample_years, climatology_quality, h_score, o_score,
  t_gate, p_gate, f_gate, latest_measurement, latest_source_update,
  evidence_class
FROM `{project}.{dataset}.hydrology_latest_v1`
WHERE (@river IS NULL OR LOWER(river)=LOWER(@river))
ORDER BY data_referencia DESC, station_code
LIMIT @limit
""".strip()


def build_ptax_current_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  data_referencia, data_publicacao, data_coleta, competencia,
  moeda, cotacao_compra, cotacao_venda, data_hora_cotacao,
  evidence_class, collector_version
FROM `{project}.{dataset}.ptax_current_v1`
WHERE (@currency IS NULL OR moeda=@currency)
ORDER BY data_referencia DESC, data_hora_cotacao DESC
LIMIT 1
""".strip()


def build_imea_freight_reference_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  snapshot_id, record_id, data_referencia, produto, metric_name,
  origem, destino, valor, unidade_origem, unidade_canonica,
  evidence_class, evidence_subtype, negotiated, data_coleta,
  route_type
FROM `{project}.{dataset}.imea_freight_reference_v1`
WHERE (@origin IS NULL OR LOWER(origem)=LOWER(@origin))
  AND (@destination IS NULL OR LOWER(destino)=LOWER(@destination))
  AND (@product IS NULL OR LOWER(produto)=LOWER(@product))
ORDER BY data_referencia DESC, origem, destino
LIMIT @limit
""".strip()

def build_crop_current_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  snapshot_id, source_id, geo_level, geo_id, product_id, safra, vintage_position,
  area_mil_ha, produtividade_kg_ha, producao_mil_t,
  previous_area_mil_ha, previous_produtividade_kg_ha, previous_producao_mil_t,
  delta_area_mil_ha, delta_area_pct,
  delta_produtividade_kg_ha, delta_produtividade_pct,
  delta_producao_mil_t, delta_producao_pct,
  data_referencia, data_publicacao, data_coleta, competencia,
  evidence_class, raw_artifact_ref, source_url, source_hash
FROM `{project}.{dataset}.crop_current_v1`
WHERE (@geo_level IS NULL OR geo_level=@geo_level)
  AND (@geo_id IS NULL OR geo_id=@geo_id)
  AND (@product IS NULL OR product_id=@product)
  AND (@safra IS NULL OR safra=@safra)
ORDER BY data_publicacao DESC, product_id, geo_id
LIMIT @limit
""".strip()


def build_freight_history_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  origin_municipality_id, destination_municipality_id, product_id, data_referencia,
  raw_offer_count, unique_offer_clusters,
  freight_brl_per_t_p50, freight_brl_per_t_previous,
  freight_brl_per_t_avg_7d, freight_brl_per_t_avg_30d,
  freight_brl_per_t_km_p50, historical_percentile,
  data_coleta, evidence_class
FROM `{project}.{dataset}.freight_history_v1`
WHERE (@origin IS NULL OR origin_municipality_id=@origin)
  AND (@destination IS NULL OR destination_municipality_id=@destination)
  AND (@product IS NULL OR product_id=@product)
ORDER BY data_referencia DESC, unique_offer_clusters DESC
LIMIT @limit
""".strip()



def build_imea_market_indicators_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  snapshot_id, record_id, source_sheet, data_referencia, produto, metric_name,
  valor, unidade_origem, unidade_canonica, local,
  previous_value, avg_7d, avg_30d, historical_percentile,
  evidence_class, evidence_subtype, negotiated, data_coleta, source_hash, raw_artifact_ref
FROM `{project}.{dataset}.imea_market_indicators_v1`
WHERE (@product IS NULL OR LOWER(produto)=LOWER(@product))
  AND (@location IS NULL OR LOWER(local)=LOWER(@location))
ORDER BY data_referencia DESC, produto, metric_name, local
LIMIT @limit
""".strip()


def build_weather_consensus_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
SELECT
  geo_id, variable, unit, valid_time,
  model_count, member_count, model_p25, model_median, model_p75,
  model_min, model_max, model_iqr,
  models_revised_up, models_revised_down, models_unchanged,
  models_with_run_comparison, data_coleta, evidence_class
FROM `{project}.{dataset}.weather_consensus_v1`
WHERE (@geo_id IS NULL OR geo_id=@geo_id)
  AND (@variable IS NULL OR variable=@variable)
  AND valid_time >= CURRENT_TIMESTAMP()
  AND valid_time <= TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
ORDER BY valid_time, variable
LIMIT @limit
""".strip()
