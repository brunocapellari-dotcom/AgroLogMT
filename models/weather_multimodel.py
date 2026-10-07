from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import median
from typing import Iterable


@dataclass(frozen=True)
class ForecastPoint:
    model: str
    run_at: datetime
    valid_at: datetime
    variable: str
    value: float
    unit: str
    ensemble_member: str | None = None


@dataclass(frozen=True)
class ModelRunChange:
    model: str
    previous_run_at: str | None
    latest_run_at: str
    previous_value: float | None
    latest_value: float
    delta: float | None


@dataclass(frozen=True)
class MultiModelConsensus:
    valid_at: str
    variable: str
    unit: str
    model_count: int
    member_count: int
    median_value: float
    min_value: float
    max_value: float
    iqr: float
    direction_agreement_share: float | None
    direction: str
    run_changes: tuple[ModelRunChange, ...]

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["run_changes"] = [asdict(item) for item in self.run_changes]
        return row


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate quantile on empty values")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _latest_member_median(rows: list[ForecastPoint]) -> float:
    return float(median([row.value for row in rows]))


def build_multimodel_consensus(
    points: Iterable[ForecastPoint],
    *,
    valid_at: datetime,
    variable: str,
) -> MultiModelConsensus:
    rows = [row for row in points if row.valid_at == valid_at and row.variable == variable]
    if not rows:
        raise ValueError("no forecast points for requested valid_at/variable")

    units = {row.unit for row in rows}
    if len(units) != 1:
        raise ValueError("forecast units must be homogeneous before consensus")
    unit = next(iter(units))

    by_model: dict[str, dict[datetime, list[ForecastPoint]]] = {}
    for row in rows:
        by_model.setdefault(row.model, {}).setdefault(row.run_at, []).append(row)

    latest_values: list[float] = []
    changes: list[ModelRunChange] = []
    signed_changes: list[int] = []

    for model in sorted(by_model):
        run_map = by_model[model]
        run_times = sorted(run_map)
        latest_run = run_times[-1]
        latest_value = _latest_member_median(run_map[latest_run])
        latest_values.append(latest_value)

        previous_run = run_times[-2] if len(run_times) >= 2 else None
        previous_value = _latest_member_median(run_map[previous_run]) if previous_run else None
        delta = None if previous_value is None else latest_value - previous_value
        if delta is not None and delta != 0:
            signed_changes.append(1 if delta > 0 else -1)

        changes.append(ModelRunChange(
            model=model,
            previous_run_at=None if previous_run is None else previous_run.isoformat(),
            latest_run_at=latest_run.isoformat(),
            previous_value=previous_value,
            latest_value=latest_value,
            delta=delta,
        ))

    q25 = _quantile(latest_values, 0.25)
    q75 = _quantile(latest_values, 0.75)

    if not signed_changes:
        direction = "NO_COMPARABLE_RUN_CHANGE"
        agreement = None
    else:
        positives = sum(item > 0 for item in signed_changes)
        negatives = sum(item < 0 for item in signed_changes)
        dominant = max(positives, negatives)
        agreement = dominant / len(signed_changes)
        if positives == negatives:
            direction = "MIXED"
        elif positives > negatives:
            direction = "UPWARD_REVISION"
        else:
            direction = "DOWNWARD_REVISION"

    latest_run_rows = []
    for model, run_map in by_model.items():
        latest_run_rows.extend(run_map[max(run_map)])

    return MultiModelConsensus(
        valid_at=valid_at.isoformat(),
        variable=variable,
        unit=unit,
        model_count=len(by_model),
        member_count=len(latest_run_rows),
        median_value=float(median(latest_values)),
        min_value=float(min(latest_values)),
        max_value=float(max(latest_values)),
        iqr=float(q75 - q25),
        direction_agreement_share=agreement,
        direction=direction,
        run_changes=tuple(changes),
    )
