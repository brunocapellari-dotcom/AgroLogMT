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


def build_agrolog360_sql_bundle(project_id: str) -> tuple[MartSql, ...]:
    return (
        climate_rollups_sql(project_id),
        storage_balance_sql(project_id),
        freight_lanes_sql(project_id),
        fertilizer_trade_sql(project_id),
        biomass_sql(project_id),
        overview_sql(project_id),
    )
