from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .feature_matrix import FeatureSnapshot, assert_snapshot_before_cutoff


@dataclass(frozen=True)
class TrainingExample:
    entity: tuple[Any, ...]
    cutoff: str
    features: dict[str, float]
    target_metric: str
    target_value: float
    target_reference_time: str
    feature_provenance: dict[str, dict[str, Any]]


def _dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def make_training_example(
    snapshot: FeatureSnapshot,
    *,
    target_metric: str,
    target_value: float,
    target_reference_time: str | datetime,
) -> TrainingExample:
    """Anexa um target futuro a um snapshot sem permitir target leakage.

    O target deve se referir a um momento posterior ao cutoff. A disponibilidade
    do target nao e usada como feature: apenas seu valor final entra na avaliacao.
    """
    assert_snapshot_before_cutoff(snapshot)
    if target_metric in snapshot.values:
        raise ValueError("target_metric aparece nas features")
    cutoff = _dt(snapshot.cutoff)
    target_time = _dt(target_reference_time)
    if target_time <= cutoff:
        raise ValueError("target_reference_time deve ser posterior ao cutoff")
    provenance = {
        metric: {
            "source_id": value.source_id,
            "available_at": value.available_at,
            "data_referencia": value.data_referencia,
            "data_publicacao": value.data_publicacao,
            "data_coleta": value.data_coleta,
            "source_hash": value.source_hash,
            "methodology_id": value.methodology_id,
        }
        for metric, value in snapshot.provenance.items()
    }
    return TrainingExample(
        entity=snapshot.entity,
        cutoff=snapshot.cutoff,
        features=dict(snapshot.values),
        target_metric=target_metric,
        target_value=float(target_value),
        target_reference_time=target_time.astimezone(timezone.utc).isoformat(),
        feature_provenance=provenance,
    )


def validate_examples(examples: Iterable[TrainingExample]) -> None:
    seen: set[tuple[Any, ...]] = set()
    for example in examples:
        key = example.entity + (example.cutoff, example.target_metric)
        if key in seen:
            raise ValueError(f"exemplo duplicado: {key}")
        seen.add(key)
        if example.target_metric in example.features:
            raise ValueError("target_metric presente nas features")
        if _dt(example.target_reference_time) <= _dt(example.cutoff):
            raise ValueError("target nao e futuro em relacao ao cutoff")
