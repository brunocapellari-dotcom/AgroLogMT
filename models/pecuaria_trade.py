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
    if not isinstance(codes, list) or not codes or not all(isinstance(code, str) and len(code) == 8 for code in codes):
        raise ValueError("contrato bovino com ncm8 invalido")
    if not isinstance(segments, dict) or not segments:
        raise ValueError("contrato bovino sem segmentos")
    segment_codes = [code for values in segments.values() for code in values]
    if set(segment_codes) != set(codes) or len(segment_codes) != len(set(segment_codes)):
        raise ValueError("segmentos bovinos devem particionar exatamente ncm8")
    if not product.get("offal_excluded"):
        raise ValueError("contrato bovino deve excluir miudezas explicitamente")
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
    if start_year < 1997:
        raise ValueError("Comex Stat detalhado moderno comeca em 1997")
    if end_year is not None and end_year < start_year:
        raise ValueError("end_year anterior a start_year")

    scope = load_beef_scope(contract_path)
    codes = list(scope["ncm8"])
    segments = scope["segments"]
    code_sql = ", ".join(f"'{code}'" for code in codes)
    when_sql = "\n".join(
        f"    WHEN co_ncm IN ({', '.join(repr(code) for code in segment_codes)}) THEN '{segment}'"
        for segment, segment_codes in segments.items()
    )
    end_filter = f"\n  AND co_ano <= {int(end_year)}" if end_year is not None else ""

    return f"""SELECT
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
  ANY_VALUE(geo_semantics) AS geo_semantics,
  ANY_VALUE(urf_semantics) AS urf_semantics
FROM `{project}.{dataset}.comexstat_ncm_export`
WHERE sg_uf_ncm = 'MT'
  AND co_ano >= {int(start_year)}{end_filter}
  AND co_ncm IN ({code_sql})
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
