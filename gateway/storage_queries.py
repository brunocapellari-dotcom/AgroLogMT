from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")
_UF = re.compile(r"^[A-Za-z]{2}$")


def safe_identifier(value: str, *, label: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} invalido")
    return value


def normalize_uf(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().upper()
    if not _UF.fullmatch(value):
        raise ValueError("UF deve conter duas letras")
    return value


def normalize_limit(value: int, *, maximum: int = 1000) -> int:
    if value < 1 or value > maximum:
        raise ValueError(f"limit deve estar entre 1 e {maximum}")
    return value


def build_latest_summary_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
WITH latest AS (
  SELECT snapshot_id
  FROM `{project}.{dataset}.armazens_conab`
  GROUP BY snapshot_id
  ORDER BY MAX(data_coleta) DESC
  LIMIT 1
)
SELECT
  MAX(data_referencia) AS data_referencia,
  COUNT(DISTINCT warehouse_id) AS quantidade_armazens,
  SUM(COALESCE(capacidade_estatica_t, 0)) AS capacidade_estatica_t,
  COUNTIF(capacidade_estatica_t IS NULL) AS registros_sem_capacidade,
  AVG(quality_score) AS quality_score_medio
FROM `{project}.{dataset}.armazens_conab`
WHERE snapshot_id = (SELECT snapshot_id FROM latest)
  AND (@uf IS NULL OR uf = @uf)
  AND (@municipio IS NULL OR LOWER(municipio) = LOWER(@municipio))
""".strip()


def build_latest_warehouses_sql(project: str, dataset: str) -> str:
    project = safe_identifier(project, label="project")
    dataset = safe_identifier(dataset, label="dataset")
    return f"""
WITH latest AS (
  SELECT snapshot_id
  FROM `{project}.{dataset}.armazens_conab`
  GROUP BY snapshot_id
  ORDER BY MAX(data_coleta) DESC
  LIMIT 1
)
SELECT
  warehouse_id, cda, razao_social, nome_armazem, municipio, uf,
  tipo_armazenagem, capacidade_estatica_t, latitude, longitude,
  data_referencia, quality_score, quality_flags
FROM `{project}.{dataset}.armazens_conab`
WHERE snapshot_id = (SELECT snapshot_id FROM latest)
  AND (@uf IS NULL OR uf = @uf)
  AND (@municipio IS NULL OR LOWER(municipio) = LOWER(@municipio))
ORDER BY capacidade_estatica_t DESC, warehouse_id
LIMIT @limit
""".strip()
