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
