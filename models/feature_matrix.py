from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .point_in_time import available_at, select_as_of


@dataclass(frozen=True)
class FeatureValue:
    metric_id: str
    value: float
    source_id: str | None
    available_at: str
    data_referencia: str | None
    data_publicacao: str | None
    data_coleta: str | None
    source_hash: str | None
    methodology_id: str | None


@dataclass(frozen=True)
class FeatureSnapshot:
    entity: tuple[Any, ...]
    cutoff: str
    values: dict[str, float]
    provenance: dict[str, FeatureValue]


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def build_feature_snapshots(
    rows: Iterable[dict[str, Any]],
    *,
    cutoff: datetime,
    entity_fields: tuple[str, ...],
    feature_metrics: tuple[str, ...],
    metric_field: str = "metric_id",
    value_field: str = "value",
    target_metric: str | None = None,
) -> list[FeatureSnapshot]:
    """Constroi uma matriz de features usando apenas dados disponiveis no cutoff.

    O registro mais recente disponivel ate o cutoff vence por entidade + metrica.
    `data_referencia` nao controla disponibilidade. Provenance e preservada por
    feature para auditoria e reproducao do dataset.
    """
    metrics = tuple(dict.fromkeys(feature_metrics))
    if not metrics:
        raise ValueError("feature_metrics vazio")
    if target_metric is not None and target_metric in metrics:
        raise ValueError("target_metric nao pode ser feature da propria previsao")

    candidate_rows = [row for row in rows if row.get(metric_field) in metrics]
    selected = select_as_of(
        candidate_rows,
        cutoff=cutoff,
        key_fields=entity_fields + (metric_field,),
        revision_field="revision",
    )

    grouped: dict[tuple[Any, ...], dict[str, dict[str, Any]]] = {}
    for row in selected:
        entity = tuple(row.get(field) for field in entity_fields)
        metric = str(row.get(metric_field))
        grouped.setdefault(entity, {})[metric] = row

    snapshots: list[FeatureSnapshot] = []
    for entity in sorted(grouped, key=lambda item: tuple("" if value is None else str(value) for value in item)):
        metric_rows = grouped[entity]
        if any(metric not in metric_rows for metric in metrics):
            continue
        values: dict[str, float] = {}
        provenance: dict[str, FeatureValue] = {}
        for metric in metrics:
            row = metric_rows[metric]
            raw_value = row.get(value_field)
            if raw_value is None:
                break
            value = float(raw_value)
            when = available_at(row)
            if when is None:
                break
            values[metric] = value
            provenance[metric] = FeatureValue(
                metric_id=metric,
                value=value,
                source_id=row.get("source_id"),
                available_at=_utc_iso(when),
                data_referencia=row.get("data_referencia"),
                data_publicacao=row.get("data_publicacao"),
                data_coleta=row.get("data_coleta"),
                source_hash=row.get("source_hash"),
                methodology_id=row.get("methodology_id"),
            )
        else:
            snapshots.append(FeatureSnapshot(
                entity=entity,
                cutoff=_utc_iso(cutoff),
                values=values,
                provenance=provenance,
            ))
    return snapshots


def assert_snapshot_before_cutoff(snapshot: FeatureSnapshot) -> None:
    cutoff = datetime.fromisoformat(snapshot.cutoff.replace("Z", "+00:00"))
    for metric, provenance in snapshot.provenance.items():
        observed = datetime.fromisoformat(provenance.available_at.replace("Z", "+00:00"))
        if observed > cutoff:
            raise ValueError(f"feature {metric} possui disponibilidade posterior ao cutoff")
