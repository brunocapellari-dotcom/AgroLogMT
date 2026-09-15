from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_CONTRACT_PATH = Path("contracts/product_trade_codes.v1.json")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} invalido: {value!r}")
    return value


def load_beef_scope(contract_path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    product = contract.get("products", {}).get("carne_bovina_in_natura")
    if not isinstance(product, dict):
        raise ValueError("contrato sem carne_bovina_in_natura")
    codes = product.get("ncm8")
    segments = product.get("segments")
    historical = product.get("historical_aggregate")
    if not isinstance(codes, list) or not codes or not all(isinstance(code, str) and len(code) == 8 for code in codes):
        raise ValueError("contrato bovino com ncm8 invalido")
    if not isinstance(segments, dict) or not segments:
        raise ValueError("contrato bovino sem segmentos")
    segment_codes = [code for values in segments.values() for code in values]
    if set(segment_codes) != set(codes) or len(segment_codes) != len(set(segment_codes)):
        raise ValueError("segmentos bovinos devem particionar exatamente ncm8")
    if not product.get("offal_excluded"):
        raise ValueError("contrato bovino deve excluir miudezas explicitamente")
    if not isinstance(historical, dict) or historical.get("basis") != "hs4_heading":
        raise ValueError("contrato bovino sem escopo historico HS4")
    headings = historical.get("headings")
    segment_by_heading = historical.get("segment_by_heading")
    if set(headings or {}) != {"0201", "0202"} or set(segment_by_heading or {}) != {"0201", "0202"}:
        raise ValueError("escopo historico bovino deve usar exatamente HS4 0201/0202")
    if historical.get("ncm8_temporal_mapping_required") is not True:
        raise ValueError("detalhe NCM8 historico deve exigir mapping temporal")
    return product


def build_mt_beef_export_query(
    *,
    project_id: str,
    dataset_id: str = "comercio_exterior",
    start_year: int = 1997,
    end_year: int | None = None,
    contract_path: str | Path = DEFAULT_CONTRACT_PATH,
) -> str:
    project = _safe_identifier(project_id, "project_id")
    dataset = _safe_identifier(dataset_id, "dataset_id")
    scope = load_beef_scope(contract_path)
    historical = scope["historical_aggregate"]
    valid_from = int(historical["valid_from"])
    if start_year < valid_from:
        raise ValueError(f"Comex Stat histórico bovino começa em {valid_from}")
    if end_year is not None and end_year < start_year:
        raise ValueError("end_year anterior a start_year")

    segment_by_heading = historical["segment_by_heading"]
    when_sql = "\n".join(
        f"    WHEN STARTS_WITH(co_ncm, '{heading}') THEN '{segment}'"
        for heading, segment in sorted(segment_by_heading.items())
    )
    heading_predicate = " OR ".join(
        f"STARTS_WITH(co_ncm, '{heading}')" for heading in sorted(historical["headings"])
    )
    end_filter = f"\n    AND co_ano <= {int(end_year)}" if end_year is not None else ""

    return f"""WITH candidate_rows AS (
  SELECT *
  FROM `{project}.{dataset}.comexstat_ncm_export`
  WHERE co_ano >= {int(start_year)}{end_filter}
),
latest_snapshot_by_year AS (
  SELECT
    co_ano,
    ARRAY_AGG(snapshot_id ORDER BY data_coleta DESC, snapshot_id DESC LIMIT 1)[OFFSET(0)] AS snapshot_id
  FROM candidate_rows
  GROUP BY co_ano
),
latest_rows AS (
  SELECT r.*
  FROM candidate_rows r
  JOIN latest_snapshot_by_year s
    ON r.co_ano=s.co_ano AND r.snapshot_id=s.snapshot_id
)
SELECT
  competencia,
  co_ano,
  co_mes,
  co_ncm,
  CASE
{when_sql}
    ELSE 'fora_escopo'
  END AS segmento_carne,
  co_pais,
  co_via,
  co_urf,
  sg_uf_ncm,
  SUM(kg_liquido) AS kg_liquido,
  SUM(toneladas) AS toneladas,
  SUM(vl_fob) AS vl_fob_usd,
  SAFE_DIVIDE(SUM(vl_fob), SUM(toneladas)) AS usd_por_t,
  ANY_VALUE(snapshot_id) AS source_snapshot_id,
  MAX(data_coleta) AS source_data_coleta,
  ANY_VALUE(geo_semantics) AS geo_semantics,
  ANY_VALUE(urf_semantics) AS urf_semantics
FROM latest_rows
WHERE sg_uf_ncm = 'MT'
  AND ({heading_predicate})
GROUP BY competencia, co_ano, co_mes, co_ncm, segmento_carne, co_pais, co_via, co_urf, sg_uf_ncm
ORDER BY competencia, co_ncm, co_pais
"""


def build_create_view_sql(
    *,
    project_id: str,
    dataset_id: str = "comercio_exterior",
    view_name: str = "v_pecuaria_mt_beef_exports",
    start_year: int = 1997,
    end_year: int | None = None,
    contract_path: str | Path = DEFAULT_CONTRACT_PATH,
) -> str:
    project = _safe_identifier(project_id, "project_id")
    dataset = _safe_identifier(dataset_id, "dataset_id")
    view = _safe_identifier(view_name, "view_name")
    query = build_mt_beef_export_query(
        project_id=project,
        dataset_id=dataset,
        start_year=start_year,
        end_year=end_year,
        contract_path=contract_path,
    )
    return f"CREATE OR REPLACE VIEW `{project}.{dataset}.{view}` AS\n{query}"
