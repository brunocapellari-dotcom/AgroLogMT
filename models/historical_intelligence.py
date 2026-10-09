from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import sqrt
from statistics import mean, median
from typing import Iterable


@dataclass(frozen=True)
class HistoricalPoint:
    reference_date: date
    value: float
    season: str | None = None
    phase: str | None = None
    vintage_id: str | None = None


@dataclass(frozen=True)
class HistoricalComparison:
    current: float
    previous: float | None
    delta_previous: float | None
    delta_previous_pct: float | None
    season_start: float | None
    delta_season_start: float | None
    prior_season_same_phase: float | None
    delta_prior_season_same_phase: float | None
    historical_mean: float | None
    historical_median: float | None
    percentile: float | None
    historical_min: float | None
    historical_max: float | None
    trend_slope_per_observation: float | None
    trend_direction: str
    sample_size: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _pct_delta(current: float, base: float | None) -> float | None:
    if base is None or base == 0:
        return None
    return (current - base) / abs(base) * 100.0


def _linear_slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    n = len(values)
    x_mean = (n - 1) / 2
    y_mean = mean(values)
    numerator = sum((i - x_mean) * (value - y_mean) for i, value in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return None if denominator == 0 else numerator / denominator


def _percentile_rank(values: list[float], current: float) -> float | None:
    if not values:
        return None
    less = sum(v < current for v in values)
    equal = sum(v == current for v in values)
    return 100.0 * (less + 0.5 * equal) / len(values)


def compare_history(
    points: Iterable[HistoricalPoint],
    *,
    current: HistoricalPoint | None = None,
    trend_window: int = 8,
) -> HistoricalComparison:
    rows = sorted(points, key=lambda item: (item.reference_date, item.vintage_id or ""))
    if not rows and current is None:
        raise ValueError("historical series is empty")
    current_point = current or rows[-1]
    if trend_window < 2:
        raise ValueError("trend_window must be >= 2")

    eligible = [row for row in rows if row.reference_date <= current_point.reference_date]
    previous_candidates = [
        row for row in eligible
        if (row.reference_date, row.vintage_id or "") < (current_point.reference_date, current_point.vintage_id or "")
    ]
    previous = previous_candidates[-1] if previous_candidates else None

    season_start = None
    if current_point.season is not None:
        same_season = [row for row in eligible if row.season == current_point.season]
        if same_season:
            season_start = same_season[0]

    prior_same_phase = None
    if current_point.season is not None and current_point.phase is not None:
        prior_candidates = [
            row for row in eligible
            if row.season not in {None, current_point.season} and row.phase == current_point.phase
        ]
        if prior_candidates:
            # last observation from the latest prior season represented in the data
            prior_season = prior_candidates[-1].season
            same = [row for row in prior_candidates if row.season == prior_season]
            prior_same_phase = same[-1] if same else None

    history_values = [
        row.value for row in eligible
        if (row.reference_date, row.vintage_id or "") != (current_point.reference_date, current_point.vintage_id or "")
    ]

    trend_rows = [row.value for row in eligible][-trend_window:]
    slope = _linear_slope(trend_rows)
    if slope is None or abs(slope) < 1e-12:
        direction = "FLAT_OR_INSUFFICIENT"
    elif slope > 0:
        direction = "RISING"
    else:
        direction = "FALLING"

    return HistoricalComparison(
        current=float(current_point.value),
        previous=None if previous is None else float(previous.value),
        delta_previous=None if previous is None else float(current_point.value - previous.value),
        delta_previous_pct=None if previous is None else _pct_delta(current_point.value, previous.value),
        season_start=None if season_start is None else float(season_start.value),
        delta_season_start=None if season_start is None else float(current_point.value - season_start.value),
        prior_season_same_phase=None if prior_same_phase is None else float(prior_same_phase.value),
        delta_prior_season_same_phase=None if prior_same_phase is None else float(current_point.value - prior_same_phase.value),
        historical_mean=None if not history_values else float(mean(history_values)),
        historical_median=None if not history_values else float(median(history_values)),
        percentile=_percentile_rank(history_values, current_point.value),
        historical_min=None if not history_values else float(min(history_values)),
        historical_max=None if not history_values else float(max(history_values)),
        trend_slope_per_observation=None if slope is None else float(slope),
        trend_direction=direction,
        sample_size=len(history_values),
    )
