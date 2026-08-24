from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class ComexRelease:
    competence: str
    release_time: str
    release_type: str
    source_url: str
    evidence_basis: str
    verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_release(
    *,
    competence: str,
    release_time: str,
    release_type: str,
    source_url: str,
    evidence_basis: str,
) -> ComexRelease:
    try:
        year_text, month_text = competence.split("-")
        year, month = int(year_text), int(month_text)
        if not 1 <= month <= 12 or year < 1997:
            raise ValueError
    except ValueError as exc:
        raise ValueError("competence deve ser YYYY-MM a partir de 1997") from exc
    parsed = datetime.fromisoformat(release_time.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("release_time deve possuir timezone explícito")
    if release_type not in {"preliminary_partial", "monthly_consolidated", "annual_definitive"}:
        raise ValueError("release_type não reconhecido")
    if not source_url.startswith("https://"):
        raise ValueError("source_url deve ser HTTPS")
    if not evidence_basis.strip():
        raise ValueError("evidence_basis obrigatório")
    return ComexRelease(
        competence=f"{year:04d}-{month:02d}",
        release_time=parsed.astimezone(timezone.utc).isoformat(),
        release_type=release_type,
        source_url=source_url,
        evidence_basis=evidence_basis,
    )


def latest_release_as_of(
    releases: Iterable[ComexRelease],
    *,
    competence: str,
    cutoff: datetime,
    consolidated_only: bool = True,
) -> ComexRelease | None:
    if cutoff.tzinfo is None:
        raise ValueError("cutoff deve possuir timezone")
    eligible = []
    for release in releases:
        if release.competence != competence or not release.verified:
            continue
        if consolidated_only and release.release_type == "preliminary_partial":
            continue
        when = datetime.fromisoformat(release.release_time)
        if when <= cutoff.astimezone(timezone.utc):
            eligible.append((when, release))
    return max(eligible, key=lambda item: item[0])[1] if eligible else None


def historical_row_is_feature_eligible(
    *,
    competence: str,
    cutoff: datetime,
    releases: Iterable[ComexRelease],
) -> bool:
    """A linha final de um CSV anual não ganha disponibilidade histórica sozinha.

    Para usar uma competência como feature em um cutoff passado, deve existir evidência
    documental da divulgação consolidada/definitiva até aquele cutoff. Isso não reconstrói
    revisões intermediárias ausentes; apenas estabelece o limite mínimo de disponibilidade.
    """
    return latest_release_as_of(releases, competence=competence, cutoff=cutoff, consolidated_only=True) is not None


def snapshot_can_reconstruct_vintage(
    *,
    snapshot_collected_at: datetime,
    release: ComexRelease,
) -> bool:
    """Só um snapshot realmente capturado próximo à divulgação reconstrói aquela vintage.

    Um arquivo baixado anos depois pode ser usado como desfecho final, mas não é tratado como
    cópia da vintage histórica apenas porque conhecemos a data de divulgação do mês.
    """
    if snapshot_collected_at.tzinfo is None:
        raise ValueError("snapshot_collected_at deve possuir timezone")
    release_dt = datetime.fromisoformat(release.release_time)
    return snapshot_collected_at.astimezone(timezone.utc) >= release_dt
