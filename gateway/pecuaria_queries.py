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
