from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


EVIDENCE_CLASSES = {"OBSERVADO", "ESTIMADO", "PREVISTO", "INFERIDO", "CENARIO"}
TREND_TYPES = {"ESTATISTICA", "FUNDAMENTAL", "PROSPECTIVA"}


@dataclass(frozen=True)
class AnalysisClaim:
    topic: str
    evidence_class: str
    evidence: str
    mechanism: str
    impact_potential: str
    horizon: str
    confidence: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        evidence_class = self.evidence_class.upper()
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"invalid evidence class: {self.evidence_class}")
        for field_name in ("topic", "evidence", "mechanism", "impact_potential", "horizon", "confidence"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if not self.source_ids:
            raise ValueError("source_ids cannot be empty")
        object.__setattr__(self, "evidence_class", evidence_class)

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["source_ids"] = list(self.source_ids)
        return row


@dataclass(frozen=True)
class TrendAssessment:
    topic: str
    trend_type: str
    direction: str
    rationale: str
    horizon: str
    confidence: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        trend_type = self.trend_type.upper()
        if trend_type not in TREND_TYPES:
            raise ValueError(f"invalid trend_type: {self.trend_type}")
        if not self.source_ids:
            raise ValueError("source_ids cannot be empty")
        object.__setattr__(self, "trend_type", trend_type)

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["source_ids"] = list(self.source_ids)
        return row


def claims_by_topic(claims: Iterable[AnalysisClaim]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for claim in claims:
        grouped.setdefault(claim.topic, []).append(claim.to_dict())
    return grouped
