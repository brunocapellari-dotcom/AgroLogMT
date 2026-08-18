from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Group = Literal["radar", "dados", "conhecimento"]
EvidenceClass = Literal["observado", "inferido", "estimado", "negociado_autorizado"]


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    name: str
    group: Group
    method: str
    enabled: bool = True
    url: str | None = None
    expected_frequency: str | None = None
    file_extension: str | None = None
    evidence_class: EvidenceClass = "observado"
    source_timezone: str = "America/Cuiaba"
    notes: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceSpec":
        required = {"source_id", "name", "group", "method"}
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"Campos obrigatorios ausentes: {', '.join(missing)}")
        if data["group"] not in {"radar", "dados", "conhecimento"}:
            raise ValueError(f"Grupo invalido: {data['group']}")
        return cls(**data)


@dataclass
class RunManifest:
    source_id: str
    group: Group
    started_at: str
    finished_at: str
    status: str
    collector_version: str
    data_coleta: str
    observed_url: str | None = None
    raw_artifact_ref: str | None = None
    sha256: str | None = None
    bytes_read: int = 0
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    changed: bool = False
    records_read: int | None = None
    records_accepted: int | None = None
    records_rejected: int | None = None
    duplicates_removed: int | None = None
    data_referencia: str | None = None
    data_publicacao: str | None = None
    competencia: str | None = None
    evidence_class: EvidenceClass = "observado"
    gap_status: str | None = None
    missing_references: list[str] = field(default_factory=list)
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
