from __future__ import annotations

from dataclasses import dataclass

from google.cloud import bigquery

from gateway.config import Settings


MAX_LIMIT = 500


class QueryValidationError(ValueError):
    """Raised when a public query parameter is outside the allowed contract."""


@dataclass(frozen=True)
class ArmazensQuery:
    sql: str
    parameters: list[bigquery.ScalarQueryParameter]
    normalized_filters: dict[str, object]


def _clean_optional(value: str | None, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        raise QueryValidationError(f"{field} excede {max_length} caracteres.")
    return cleaned


def build_armazens_query(
    settings: Settings,
    *,
    uf: str | None = None,
    municipio: str | None = None,
    identificacao_armazem: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> ArmazensQuery:
    if not 1 <= limit <= MAX_LIMIT:
        raise QueryValidationError(f"limit deve estar entre 1 e {MAX_LIMIT}.")
    if offset < 0:
        raise QueryValidationError("offset não pode ser negativo.")

    uf_norm = _clean_optional(uf, field="uf", max_length=2)
    if uf_norm is not None:
        uf_norm = uf_norm.upper()
        if len(uf_norm) != 2 or not uf_norm.isalpha():
            raise QueryValidationError("uf deve conter exatamente duas letras.")

    municipio_norm = _clean_optional(municipio, field="municipio", max_length=120)
    identificacao_norm = _clean_optional(
        identificacao_armazem,
        field="identificacao_armazem",
        max_length=180,
    )

    where = ["1 = 1"]
    parameters: list[bigquery.ScalarQueryParameter] = []

    if uf_norm:
        where.append("uf = @uf")
        parameters.append(bigquery.ScalarQueryParameter("uf", "STRING", uf_norm))
    if municipio_norm:
        where.append("LOWER(municipio) = LOWER(@municipio)")
        parameters.append(bigquery.ScalarQueryParameter("municipio", "STRING", municipio_norm))
    if identificacao_norm:
        where.append("identificacao_armazem = @identificacao_armazem")
        parameters.append(
            bigquery.ScalarQueryParameter(
                "identificacao_armazem",
                "STRING",
                identificacao_norm,
            )
        )

    parameters.extend(
        [
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset),
        ]
    )

    sql = f"""
SELECT
  hash_chave_armazem,
  identificacao_armazem,
  uf,
  municipio,
  capacidade_estatica_t,
  snapshot_id_atual,
  data_snapshot_atual,
  coleta_snapshot_em_utc
FROM `{settings.armazens_table_ref}`
WHERE {' AND '.join(where)}
ORDER BY uf, municipio, identificacao_armazem
LIMIT @limit OFFSET @offset
""".strip()

    return ArmazensQuery(
        sql=sql,
        parameters=parameters,
        normalized_filters={
            "uf": uf_norm,
            "municipio": municipio_norm,
            "identificacao_armazem": identificacao_norm,
            "limit": limit,
            "offset": offset,
        },
    )
