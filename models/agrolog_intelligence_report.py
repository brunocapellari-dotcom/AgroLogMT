from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence


SECTION_ORDER = (
    "Resumo executivo",
    "O que mudou",
    "Mercado",
    "Soja",
    "Milho",
    "Safra Brasil",
    "Mato Grosso",
    "USDA/EUA",
    "Argentina",
    "Meteorologia",
    "Agroclima",
    "Previsão 3 dias",
    "Previsão 7 dias",
    "Previsão 15 dias",
    "Tendência sub-sazonal/sazonal",
    "Fretes",
    "Corredores",
    "Logística",
    "Exportação",
    "Riscos",
    "Oportunidades",
    "Tendências",
    "Anos análogos",
    "Cenário 7 dias",
    "Cenário 15 dias",
    "Cenário 30 dias",
    "Próximos eventos",
    "Fontes",
    "Metodologia",
    "Limitações",
)

CRITICAL_SECTIONS = {
    "Resumo executivo",
    "O que mudou",
    "Mercado",
    "Soja",
    "Milho",
    "Safra Brasil",
    "Mato Grosso",
    "Meteorologia",
    "Agroclima",
    "Fretes",
    "Logística",
    "Fontes",
}


@dataclass(frozen=True)
class ReportSection:
    title: str
    status: str
    summary: str
    bullets: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["bullets"] = list(self.bullets)
        row["source_ids"] = list(self.source_ids)
        return row


@dataclass(frozen=True)
class SellabilityResult:
    status: str
    blockers: tuple[str, ...]
    ready_sections: int
    total_sections: int

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["blockers"] = list(self.blockers)
        return row


def evaluate_sellability(sections: Mapping[str, ReportSection]) -> SellabilityResult:
    blockers: list[str] = []
    for title in SECTION_ORDER:
        section = sections.get(title)
        if section is None:
            blockers.append(f"missing_section:{title}")
            continue
        if title in CRITICAL_SECTIONS and section.status != "READY":
            blockers.append(f"critical_not_ready:{title}:{section.status}")
        if title in CRITICAL_SECTIONS and not (section.summary.strip() or section.bullets):
            blockers.append(f"critical_empty:{title}")
    ready = sum(1 for title in SECTION_ORDER if sections.get(title) and sections[title].status == "READY")
    return SellabilityResult(
        status="SELLABLE" if not blockers else "BLOCKED",
        blockers=tuple(blockers),
        ready_sections=ready,
        total_sections=len(SECTION_ORDER),
    )


def render_markdown(
    sections: Mapping[str, ReportSection],
    *,
    cutoff_at: datetime | None = None,
    freshness: Mapping[str, str] | None = None,
) -> tuple[str, SellabilityResult]:
    cutoff = cutoff_at or datetime.now(timezone.utc)
    gate = evaluate_sellability(sections)
    lines = [
        "# AGROLOG INTELLIGENCE",
        "",
        "## RELATÓRIO INTEGRADO AGROLOG",
        "",
        f"**Data/hora de corte:** {cutoff.isoformat()}",
        f"**Status comercial:** {gate.status}",
    ]
    if gate.blockers:
        lines.append(f"**Bloqueios:** {', '.join(gate.blockers)}")
    if freshness:
        lines.extend(["", "**Freshness:**"])
        for source_id, status in sorted(freshness.items()):
            lines.append(f"- {source_id}: {status}")

    for index, title in enumerate(SECTION_ORDER, start=1):
        section = sections.get(title)
        lines.extend(["", f"## {index}. {title}"])
        if section is None:
            lines.extend(["", "**Status:** SOURCE_GAP", "", "Sem evidência suficiente para esta seção no corte atual."])
            continue
        lines.extend(["", f"**Status:** {section.status}", "", section.summary.strip() or "Sem síntese material."])
        for bullet in section.bullets:
            lines.append(f"- {bullet}")
        if section.source_ids:
            lines.append(f"- Fontes: {', '.join(section.source_ids)}")

    return "\n".join(lines).rstrip() + "\n", gate
