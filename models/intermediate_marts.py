from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def _safe(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid identifier: {value!r}")
    return value


@dataclass(frozen=True)
class IntermediateMartSql:
    mart_id: str
    target: str
    sql: str
    materialization: str = "CREATE_OR_REPLACE_VIEW"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _qualify(project_id: str, short_name: str) -> str:
    project = _safe(project_id)
    parts = short_name.split(".")
    if len(parts) != 2:
        raise ValueError(f"expected dataset.table: {short_name}")
    return f"`{project}.{_safe(parts[0])}.{_safe(parts[1])}`"


def production_sql(project_id: str) -> IntermediateMartSql:
    source = _qualify(project_id, "agro.conab_safra_graos")
    target_name = "marts_soy_mt.production_v1"
    target = _qualify(project_id, target_name)
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  snapshot_id, record_id, source_id, geo_level, geo_id, safra, vintage_position,
  area_mil_ha, produtividade_kg_ha, producao_mil_t,
  data_referencia, data_publicacao, data_coleta, data_disponibilidade,
  availability_verified, availability_basis, competencia, evidence_class,
  methodology_id, source_hash, quality_score, quality_flags
FROM {source}
WHERE product_id='soja' AND geo_id IN ('MT','BR')
""".strip()
    return IntermediateMartSql("soy_mt_production", target_name, sql)


def storage_sql(project_id: str) -> IntermediateMartSql:
    source = _qualify(project_id, "logistica.armazens_conab")
    geo = _qualify(project_id, "referencia.municipios_ibge")
    target_name = "marts_soy_mt.storage_v1"
    target = _qualify(project_id, target_name)
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  a.snapshot_id, a.record_id, a.warehouse_id, a.cda, a.cnpj, a.razao_social,
  a.nome_armazem, a.municipio, a.uf, a.codigo_ibge, a.tipo_armazenagem,
  a.capacidade_estatica_t, a.latitude, a.longitude,
  a.data_referencia, a.data_publicacao, a.data_coleta, a.competencia,
  a.evidence_class, a.source_hash, a.quality_score, a.quality_flags,
  g.codigo_ibge AS geo_id_canonico
FROM {source} a
LEFT JOIN {geo} g ON CAST(a.codigo_ibge AS STRING)=CAST(g.codigo_ibge AS STRING)
WHERE a.uf='MT'
""".strip()
    return IntermediateMartSql("soy_mt_storage", target_name, sql)


def market_sql(project_id: str) -> IntermediateMartSql:
    source = _qualify(project_id, "mercado.imea_indicadores_operacionais")
    target_name = "marts_soy_mt.market_v1"
    target = _qualify(project_id, target_name)
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT *
FROM {source}
WHERE UPPER(produto)='SOJA'
""".strip()
    return IntermediateMartSql("soy_mt_market", target_name, sql)


def trade_sql(project_id: str, *, soybean_ncm_codes: tuple[str, ...]) -> IntermediateMartSql:
    if not soybean_ncm_codes:
        raise ValueError("soybean_ncm_codes cannot be empty")
    for code in soybean_ncm_codes:
        if not re.fullmatch(r"[0-9]{8}", code):
            raise ValueError(f"invalid NCM code: {code}")
    source = _qualify(project_id, "comercio_exterior.comexstat_ncm_export")
    target_name = "marts_soy_mt.trade_v1"
    target = _qualify(project_id, target_name)
    quoted = ",".join(f"'{code}'" for code in soybean_ncm_codes)
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT
  snapshot_id, record_id, competencia, co_ano, co_mes, co_ncm, co_pais,
  sg_uf_ncm, co_via, co_urf, kg_liquido, toneladas, vl_fob, usd_por_t,
  geo_semantics, urf_semantics, evidence_class, data_publicacao, data_coleta,
  source_hash
FROM {source}
WHERE co_ncm IN ({quoted})
  AND (sg_uf_ncm='MT' OR sg_uf_ncm IS NULL)
""".strip()
    return IntermediateMartSql("soy_mt_trade", target_name, sql)


def climate_sql(project_id: str, *, source_table: str = "clima.nasa_power_daily") -> IntermediateMartSql:
    source = _qualify(project_id, source_table)
    target_name = "marts_soy_mt.climate_v1"
    target = _qualify(project_id, target_name)
    sql = f"""CREATE OR REPLACE VIEW {target} AS
SELECT *
FROM {source}
""".strip()
    return IntermediateMartSql("soy_mt_climate", target_name, sql)


def build_sql_bundle(project_id: str, *, soybean_ncm_codes: tuple[str, ...], climate_source: str = "clima.nasa_power_daily") -> tuple[IntermediateMartSql, ...]:
    return (
        production_sql(project_id), storage_sql(project_id), market_sql(project_id),
        trade_sql(project_id, soybean_ncm_codes=soybean_ncm_codes),
        climate_sql(project_id, source_table=climate_source),
    )
