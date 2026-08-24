from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable


def _dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def available_at(row: dict[str, Any]) -> datetime | None:
    """Momento em que um registro podia ser conhecido no mundo real.

    Regra padrão conservadora: usa o maior valor entre `data_publicacao` e
    `data_coleta`. Isso impede que uma fonte recém-coletada seja tratada como
    disponível antes de o pipeline tê-la observado.

    Exceção explícita para backfill histórico verificável: quando
    `availability_verified=true` e `data_disponibilidade` existe, esse timestamp
    representa evidência documental de que o artefato já estava publicamente
    disponível naquele momento. `data_coleta` continua preservando quando o
    AgroLog efetivamente baixou o arquivo; não é reescrita para simular coleta
    antiga.
    """
    verified = row.get("availability_verified") is True
    historical_availability = _dt(row.get("data_disponibilidade"))
    if verified and historical_availability is not None:
        return historical_availability

    publication = _dt(row.get("data_publicacao"))
    collection = _dt(row.get("data_coleta"))
    if publication and collection:
        return max(publication, collection)
    return publication or collection


def select_as_of(
    rows: Iterable[dict[str, Any]],
    *,
    cutoff: datetime,
    key_fields: tuple[str, ...],
    revision_field: str | None = None,
) -> list[dict[str, Any]]:
    """Seleciona a última vintage disponível até `cutoff` por chave lógica."""
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    chosen: dict[tuple[Any, ...], tuple[datetime, int, dict[str, Any]]] = {}
    for row in rows:
        when = available_at(row)
        if when is None or when > cutoff:
            continue
        key = tuple(row.get(field) for field in key_fields)
        revision = int(row.get(revision_field) or 0) if revision_field else 0
        previous = chosen.get(key)
        if previous is None or (when, revision) > (previous[0], previous[1]):
            chosen[key] = (when, revision, row)
    return [item[2] for item in chosen.values()]
