from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from gateway.commercial_freshness import component_freshness
from models.commercial_analysis import build_derived_components

from collector.local_analytics_store import LocalAnalyticsStore

BASE_COMPONENTS = (
    ("overview", "local.marts.overview_current"),
    ("ptax", "local.mercado.ptax_usd_daily"),
    ("market_reference", "local.marts.market_reference"),
    ("crops_mt", "local.marts.crop_current"),
    ("crops_br", "local.marts.crop_current"),
    ("crop_progress", "local.marts.crop_progress_current"),
    ("argentina", "local.marts.argentina_crop_current"),
    ("usda", "local.marts.usda_wasde_changes"),
    ("exports", "local.marts.agricultural_exports"),
    ("freight", "local.marts.freight_history"),
    ("weather", "local.marts.weather_consensus"),
    ("weather_3d", "local.marts.weather_consensus"),
    ("weather_7d", "local.marts.weather_consensus"),
    ("weather_15d", "local.marts.weather_consensus"),
    ("hydrology", "local.marts.hydrology_latest"),
)


def _component(name: str, source_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    status, latest_at, age_minutes = component_freshness(name, rows)
    return {
        "component": name,
        "source_id": source_id,
        "status": status,
        "latest_at": latest_at,
        "age_minutes": age_minutes,
        "data": rows,
    }


def _ptax(store: LocalAnalyticsStore) -> list[dict[str, Any]]:
    if not store.table_exists("mercado", "ptax_usd_daily"):
        return []
    return store.query(
        """
        SELECT * FROM mercado.ptax_usd_daily
        WHERE moeda='USD'
        ORDER BY data_hora_cotacao DESC
        LIMIT 1
        """
    )


def _exports(store: LocalAnalyticsStore, uf: str) -> list[dict[str, Any]]:
    if not store.table_exists("comercio_exterior", "comexstat_trade_monthly"):
        return []
    return store.query(
        """
        WITH mapped AS (
          SELECT
            competencia,
            state_name,
            kg_liquido / 1000.0 AS toneladas,
            valor_fob_usd AS vl_fob,
            data_publicacao,
            data_coleta,
            CASE
              WHEN ncm_code IN ('12011000','12019000') THEN 'soja_grao'
              WHEN ncm_code IN ('23040010','23040090') THEN 'farelo_soja'
              WHEN ncm_code IN ('15071000','15079011','15079019','15079090') THEN 'oleo_soja'
              WHEN ncm_code='10059010' THEN 'milho_grao'
              WHEN ncm_code IN ('52010010','52010020','52010090') THEN 'algodao_bruto'
              ELSE NULL
            END AS product_id
          FROM comercio_exterior.comexstat_trade_monthly
          WHERE flow='export'
        ),
        aggregated AS (
          SELECT
            competencia,
            product_id,
            SUM(toneladas) AS toneladas,
            SUM(vl_fob) AS vl_fob,
            SUM(vl_fob) / NULLIF(SUM(toneladas),0) AS usd_por_t,
            MAX(data_publicacao) AS data_publicacao,
            MAX(data_coleta) AS data_coleta
          FROM mapped
          WHERE product_id IS NOT NULL AND lower(state_name)='mato grosso'
          GROUP BY competencia, product_id
        )
        SELECT
          'uf' AS geo_level,
          ? AS geo_id,
          *,
          LAG(toneladas) OVER (PARTITION BY product_id ORDER BY competencia) AS previous_toneladas,
          toneladas - LAG(toneladas) OVER (PARTITION BY product_id ORDER BY competencia) AS delta_toneladas,
          CASE
            WHEN ABS(LAG(toneladas) OVER (PARTITION BY product_id ORDER BY competencia)) > 0
            THEN 100.0 * (
              toneladas - LAG(toneladas) OVER (PARTITION BY product_id ORDER BY competencia)
            ) / ABS(LAG(toneladas) OVER (PARTITION BY product_id ORDER BY competencia))
            ELSE NULL
          END AS delta_toneladas_pct,
          'OBSERVADO_COMEXSTAT' AS evidence_class
        FROM aggregated
        ORDER BY competencia DESC, product_id
        LIMIT 200
        """,
        [uf],
    )


def _crops(store: LocalAnalyticsStore, *, geo_level: str, geo_id: str) -> list[dict[str, Any]]:
    if not store.table_exists("agro", "conab_safra"):
        return []
    return store.query(
        """
        WITH latest AS (
          SELECT snapshot_id
          FROM agro.conab_safra
          GROUP BY snapshot_id
          ORDER BY MAX(data_coleta) DESC
          LIMIT 1
        )
        SELECT
          snapshot_id,
          record_id,
          source_id,
          geo_level,
          geo_id,
          produto_origem,
          product_id,
          safra,
          vintage_position,
          area_mil_ha,
          produtividade_kg_ha,
          producao_mil_t,
          area_var_pct,
          produtividade_var_pct,
          producao_var_pct,
          producao_var_pct AS delta_producao_pct,
          identity_error_mil_t,
          identity_error_pct,
          quality_score,
          quality_flags_json,
          data_referencia,
          data_publicacao,
          data_coleta,
          competencia,
          evidence_class,
          source_url,
          source_hash,
          raw_artifact_ref
        FROM agro.conab_safra
        WHERE snapshot_id=(SELECT snapshot_id FROM latest)
          AND geo_level=?
          AND geo_id=?
        ORDER BY product_id, vintage_position, safra
        """,
        [geo_level, geo_id],
    )


def _hydrology(store: LocalAnalyticsStore) -> list[dict[str, Any]]:
    if not store.table_exists("hidrologia", "hydro_station_telemetry"):
        return []
    return store.query(
        """
        SELECT
          station_code,
          station_name,
          river,
          data_referencia,
          cota_cm AS stage_cm,
          vazao_m3s AS flow_m3s,
          chuva_mm,
          data_hora_medicao AS latest_measurement,
          data_atualizacao AS latest_source_update,
          data_coleta,
          evidence_class
        FROM (
          SELECT *,
            ROW_NUMBER() OVER (
              PARTITION BY station_code
              ORDER BY data_hora_medicao DESC, data_coleta DESC
            ) AS rn
          FROM hidrologia.hydro_station_telemetry
        )
        WHERE rn=1
        ORDER BY river, station_code
        """
    )


def _argentina(store: LocalAnalyticsStore) -> list[dict[str, Any]]:
    if not store.table_exists("agro", "argentina_estimaciones"):
        return []
    return store.query(
        """
        WITH snapshot_country AS (
          SELECT
            snapshot_id,
            source_id,
            crop_id,
            season,
            reference_year,
            SUM(planted_area_ha) AS planted_area_ha,
            SUM(harvested_area_ha) AS harvested_area_ha,
            SUM(production_t) AS production_t,
            1000.0 * SUM(production_t) / NULLIF(SUM(harvested_area_ha),0) AS yield_kg_ha,
            MIN(evidence_class) AS evidence_class,
            MIN(source_url) AS source_url,
            MIN(source_hash) AS source_hash,
            MAX(data_coleta) AS data_coleta
          FROM agro.argentina_estimaciones
          WHERE crop_id IN ('soja','milho','trigo','algodao')
          GROUP BY snapshot_id, source_id, crop_id, season, reference_year
        ),
        ordered AS (
          SELECT *,
            LAG(planted_area_ha) OVER w AS previous_planted_area_ha,
            LAG(harvested_area_ha) OVER w AS previous_harvested_area_ha,
            LAG(production_t) OVER w AS previous_production_t,
            LAG(yield_kg_ha) OVER w AS previous_yield_kg_ha
          FROM snapshot_country
          WINDOW w AS (
            PARTITION BY crop_id, season
            ORDER BY data_coleta, snapshot_id
          )
        ),
        enriched AS (
          SELECT *,
            production_t - previous_production_t AS delta_production_t,
            CASE
              WHEN ABS(previous_production_t) > 0
              THEN 100.0 * (production_t - previous_production_t) / ABS(previous_production_t)
              ELSE NULL
            END AS delta_production_pct,
            yield_kg_ha - previous_yield_kg_ha AS delta_yield_kg_ha
          FROM ordered
        )
        SELECT * EXCLUDE (rn)
        FROM (
          SELECT *,
            ROW_NUMBER() OVER (
              PARTITION BY crop_id, season
              ORDER BY data_coleta DESC, snapshot_id DESC
            ) AS rn
          FROM enriched
        )
        WHERE rn=1
        ORDER BY crop_id, season DESC
        LIMIT 100
        """
    )


def _usda(store: LocalAnalyticsStore) -> list[dict[str, Any]]:
    if not store.table_exists("global_market", "usda_wasde_cells"):
        return []
    return store.query(
        r"""
        WITH ordered AS (
          SELECT *,
            CASE
              WHEN regexp_matches(lower(path || ' ' || attributes_json), '\bsoy(bean|beans)?\b') THEN 'soja'
              WHEN regexp_matches(lower(path || ' ' || attributes_json), '\b(corn|maize)\b') THEN 'milho'
              WHEN regexp_matches(lower(path || ' ' || attributes_json), '\bwheat\b') THEN 'trigo'
              WHEN regexp_matches(lower(path || ' ' || attributes_json), '\bcotton\b') THEN 'algodao'
              ELSE NULL
            END AS commodity_hint,
            LAG(numeric_value) OVER (
              PARTITION BY semantic_key
              ORDER BY release_year, release_month,
                       COALESCE(publication_date, make_date(release_year, release_month, 1)),
                       data_coleta
            ) AS previous_numeric_value
          FROM global_market.usda_wasde_cells
        ),
        latest_release AS (
          SELECT MAX(make_date(release_year, release_month, 1)) AS release_month_date
          FROM ordered
        )
        SELECT
          snapshot_id,
          semantic_key,
          semantic_occurrence,
          cell_index,
          source_id,
          release_year,
          release_month,
          publication_date,
          path,
          attributes_json,
          raw_text,
          numeric_value,
          previous_numeric_value,
          numeric_value - previous_numeric_value AS delta_numeric_value,
          commodity_hint,
          evidence_class,
          source_url,
          source_hash,
          data_coleta
        FROM ordered
        WHERE make_date(release_year, release_month, 1)=(
          SELECT release_month_date FROM latest_release
        )
          AND commodity_hint IS NOT NULL
        ORDER BY commodity_hint, path, semantic_occurrence
        LIMIT 500
        """
    )


def build_zero_cost_snapshot(store: LocalAnalyticsStore, *, uf: str = "MT") -> dict[str, Any]:
    loaders = {
        "ptax": lambda: _ptax(store),
        "crops_mt": lambda: _crops(store, geo_level="uf", geo_id=uf),
        "crops_br": lambda: _crops(store, geo_level="country", geo_id="BR"),
        "exports": lambda: _exports(store, uf),
        "hydrology": lambda: _hydrology(store),
        "argentina": lambda: _argentina(store),
        "usda": lambda: _usda(store),
    }
    components: list[dict[str, Any]] = []
    for name, source_id in BASE_COMPONENTS:
        try:
            rows = loaders[name]() if name in loaders else []
            components.append(_component(name, source_id, rows))
        except Exception:
            components.append(_component(name, source_id, []))

    components.extend(build_derived_components(components))
    failed = [item["component"] for item in components if item["status"] == "FAILED"]
    stale = [item["component"] for item in components if item["status"] == "STALE"]
    return {
        "product": "AGROLOG INTELLIGENCE",
        "delivery_mode": "ZERO_COST",
        "analytical_backend": "duckdb",
        "uf": uf,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_ANALYSIS" if not failed and not stale else "PARTIAL",
        "failed_components": failed,
        "stale_components": stale,
        "freshness": {str(item["source_id"]): str(item["status"]) for item in components},
        "components": components,
    }
