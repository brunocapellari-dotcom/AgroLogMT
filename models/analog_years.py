from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Mapping


@dataclass(frozen=True)
class AnalogCandidate:
    year: str
    distance: float
    feature_coverage: float
    compared_features: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["compared_features"] = list(self.compared_features)
        return row


@dataclass(frozen=True)
class AnalogResult:
    status: str
    methodology_id: str
    candidates: tuple[AnalogCandidate, ...]
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "methodology_id": self.methodology_id,
            "rejection_reason": self.rejection_reason,
            "candidates": [item.to_dict() for item in self.candidates],
        }


def find_analog_years(
    current: Mapping[str, float | None],
    history: Mapping[str, Mapping[str, float | None]],
    *,
    top_n: int = 3,
    min_features: int = 3,
    min_history_years: int = 5,
) -> AnalogResult:
    if top_n < 1:
        raise ValueError("top_n must be >= 1")
    if len(history) < min_history_years:
        return AnalogResult("REJECTED", "STANDARDIZED_EUCLIDEAN_V1", (), "insufficient_history_years")

    common_features = [
        key for key, value in current.items()
        if value is not None and sum(year.get(key) is not None for year in history.values()) >= min_history_years
    ]
    if len(common_features) < min_features:
        return AnalogResult("REJECTED", "STANDARDIZED_EUCLIDEAN_V1", (), "insufficient_common_features")

    scales: dict[str, tuple[float, float]] = {}
    for feature in common_features:
        values = [float(row[feature]) for row in history.values() if row.get(feature) is not None]
        sigma = pstdev(values)
        scales[feature] = (mean(values), sigma if sigma > 1e-12 else 1.0)

    candidates: list[AnalogCandidate] = []
    for year, row in history.items():
        compared = [feature for feature in common_features if row.get(feature) is not None]
        coverage = len(compared) / len(common_features)
        if len(compared) < min_features or coverage < 0.7:
            continue
        squared = []
        for feature in compared:
            _, sigma = scales[feature]
            squared.append(((float(current[feature]) - float(row[feature])) / sigma) ** 2)
        distance = sqrt(sum(squared) / len(squared))
        candidates.append(AnalogCandidate(year, distance, coverage, tuple(compared)))

    if not candidates:
        return AnalogResult("REJECTED", "STANDARDIZED_EUCLIDEAN_V1", (), "no_candidate_passed_coverage")

    candidates.sort(key=lambda item: (item.distance, -item.feature_coverage, item.year))
    return AnalogResult("READY", "STANDARDIZED_EUCLIDEAN_V1", tuple(candidates[:top_n]))
