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
    rows = store.query(
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
    return rows


def build_zero_cost_snapshot(store: LocalAnalyticsStore, *, uf: str = "MT") -> dict[str, Any]:
    loaders = {
        "ptax": lambda: _ptax(store),
        "exports": lambda: _exports(store, uf),
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
