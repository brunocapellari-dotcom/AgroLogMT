from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ProvenanceRecord:
    source_id: str
    reference_date: str
    publication_date: str | None
    collection_date: str
    competence_date: str | None
    raw_value: Any
    normalized_value: Any
    evidence_class: str
    document: str | None = None
    page: str | None = None
    table: str | None = None
    source_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.reference_date:
            raise ValueError("reference_date is required")
        if not self.collection_date:
            raise ValueError("collection_date is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def freshness_status(
    *,
    collection_date: str | None,
    max_age_minutes: int,
    now: datetime | None = None,
    failed: bool = False,
) -> str:
    if failed:
        return "FAILED"
    if not collection_date:
        return "FAILED"
    if max_age_minutes <= 0:
        raise ValueError("max_age_minutes must be positive")
    dt = datetime.fromisoformat(collection_date.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    reference_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = max(0.0, (reference_now - dt.astimezone(timezone.utc)).total_seconds() / 60)
    return "FRESH" if age <= max_age_minutes else "STALE"
