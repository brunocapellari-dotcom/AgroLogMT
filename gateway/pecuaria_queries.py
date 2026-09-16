from __future__ import annotations

import json
from pathlib import Path

from .storage_queries import safe_identifier


def load_beef_ncms(contract_path: str | Path) -> tuple[str, ...]:
    payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    product = payload.get("products", {}).get("carne_bovina_in_natura")
    if not isinstance(product, dict):
        raise ValueError("contrato sem carne_bovina_in_natura")
    codes = tuple(str(code) for code in product.get("ncm8", []))
    if not codes or any(len(code) != 8 or not code.isdigit() for code in codes):
        raise ValueError("contrato bovino com NCM inválido")
    if len(codes) != len(set(codes)):
        raise ValueError("contrato bovino com NCM duplicado")
    if not product.get("offal_excluded"):
        raise ValueError("contrato bovino deve excluir miudezas")
    historical = product.get("historical_aggregate")
    if not isinstance(historical, dict) or set(historical.get("headings") or {}) != {"0201", "0202"}:
        raise ValueError("contrato bovino sem agregado histórico HS4 0201/0202")
    return tuple(sorted(codes))


def build_cattle_state_history_sql(project_id: str, dataset_id: str) -> str:
    project = safe_identifier(project_id, label="project")
    dataset = safe_identifier(dataset_id, label="dataset")
    return f"""
SELECT
  year,
  data_referencia,
  municipios_observados,
  rebanho_bovino_cabecas,
  unit,
  ultima_coleta,
  historical_pit_guard_preserved
FROM `{project}.{dataset}.v_ibge_ppm_cattle_mt_state_year`
WHERE (@year_start IS NULL OR year >= @year_start)
  AND (@year_end IS NULL OR year <= @year_end)
ORDER BY year DESC
LIMIT @limit
"""


def build_cattle_municipal_history_sql(project_id: str, dataset_id: str) -> str:
    project = safe_identifier(project_id, label="project")
    dataset = safe_identifier(dataset_id, label="dataset")
    return f"""
SELECT
  year,
  data_referencia,
  geo_code_ibge,
  geo_name,
  value AS rebanho_bovino_cabecas,
  unit,
  data_coleta,
  availability_verified,
  point_in_time_feature_eligible,
  evidence_class
FROM `{project}.{dataset}.v_ibge_ppm_cattle_mt_latest`
WHERE (@ibge_code IS NULL OR geo_code_ibge = @ibge_code)
  AND (@municipio_pattern IS NULL OR LOWER(geo_name) LIKE @municipio_pattern)
  AND (@year_start IS NULL OR year >= @year_start)
  AND (@year_end IS NULL OR year <= @year_end)
ORDER BY year DESC, geo_name
LIMIT @limit
"""


def build_slaughter_quarterly_sql(project_id: str, dataset_id: str) -> str:
    project = safe_identifier(project_id, label="project")
    dataset = safe_identifier(dataset_id, label="dataset")
    return f"""
SELECT
  year,
  quarter,
  data_referencia,
  animais_abatidos_cabecas,
  peso_carcacas_kg,
  peso_medio_carcaca_kg_cabeca,
  ultima_coleta,
  historical_pit_guard_preserved
FROM `{project}.{dataset}.v_ibge_slaughter_cattle_mt_quarterly`
WHERE (@year_start IS NULL OR year >= @year_start)
  AND (@year_end IS NULL OR year <= @year_end)
  AND (@quarter IS NULL OR quarter = @quarter)
ORDER BY year DESC, quarter DESC
LIMIT @limit
"""


def build_sigsif_current_sql(project_id: str, dataset_id: str) -> str:
    project = safe_identifier(project_id, label="project")
    dataset = safe_identifier(dataset_id, label="dataset")
    return f"""
SELECT
  snapshot_date,
  data_coleta,
  machos,
  femeas,
  total_bovinos,
  participacao_femeas,
  temporal_semantics
FROM `{project}.{dataset}.v_mapa_sigsif_slaughter_snapshot_mt_summary`
LIMIT 1
"""


def build_beef_exports_sql(project_id: str, dataset_id: str) -> str:
    project = safe_identifier(project_id, label="project")
    dataset = safe_identifier(dataset_id, label="dataset")
    return f"""
SELECT
  competencia,
  ncm_code,
  ncm_name,
  country_code,
  country_name,
  via_code,
  via_name,
  urf_code,
  urf_name,
  kg_liquido,
  valor_fob_usd,
  SAFE_DIVIDE(valor_fob_usd, kg_liquido / 1000.0) AS usd_por_t,
  data_publicacao,
  data_coleta,
  evidence_class
FROM `{project}.{dataset}.v_comexstat_trade_monthly_latest`
WHERE state_name = 'Mato Grosso'
  AND flow = 'export'
  AND ncm_code IN UNNEST(@ncms)
  AND (@competencia_start IS NULL OR competencia >= @competencia_start)
  AND (@competencia_end IS NULL OR competencia <= @competencia_end)
  AND (@country_code IS NULL OR country_code = @country_code)
ORDER BY competencia DESC, valor_fob_usd DESC, ncm_code
LIMIT @limit
"""


def build_beef_export_history_sql(project_id: str, dataset_id: str) -> str:
    project = safe_identifier(project_id, label="project")
    dataset = safe_identifier(dataset_id, label="dataset")
    return f"""
SELECT
  competencia,
  co_ano AS year,
  co_mes AS month,
  co_ncm AS ncm_code,
  segmento_carne,
  co_pais AS country_code,
  co_via AS via_code,
  co_urf AS urf_code,
  kg_liquido,
  toneladas,
  vl_fob_usd,
  usd_por_t,
  geo_semantics,
  urf_semantics
FROM `{project}.{dataset}.v_pecuaria_mt_beef_exports`
WHERE (@year_start IS NULL OR co_ano >= @year_start)
  AND (@year_end IS NULL OR co_ano <= @year_end)
  AND (@segmento IS NULL OR segmento_carne = @segmento)
  AND (@country_code IS NULL OR CAST(co_pais AS STRING) = @country_code)
ORDER BY competencia DESC, vl_fob_usd DESC, co_ncm
LIMIT @limit
"""
