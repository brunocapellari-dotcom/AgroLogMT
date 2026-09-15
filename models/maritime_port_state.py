from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable


class MaritimePhysicalState(IntEnum):
    PROGRAMADO = 10
    EM_VIAGEM = 20
    APROXIMACAO = 30
    AREA_PORTUARIA = 40
    FUNDEADO = 50
    AGUARDANDO = 60
    MANOBRA = 70
    ATRACADO = 80
    OPERANDO = 90
    CONCLUIDO = 100
    DESATRACADO = 110
    SAIU = 120


# States that may be asserted only from explicit official/operational evidence.
OFFICIAL_EVIDENCE_REQUIRED = frozenset({
    MaritimePhysicalState.OPERANDO,
    MaritimePhysicalState.CONCLUIDO,
})

# AIS can support these states, but one isolated AIS message is never enough.
AIS_CORROBORATION_REQUIRED = frozenset({
    MaritimePhysicalState.EM_VIAGEM,
    MaritimePhysicalState.APROXIMACAO,
    MaritimePhysicalState.AREA_PORTUARIA,
    MaritimePhysicalState.FUNDEADO,
    MaritimePhysicalState.AGUARDANDO,
    MaritimePhysicalState.MANOBRA,
    MaritimePhysicalState.ATRACADO,
    MaritimePhysicalState.DESATRACADO,
    MaritimePhysicalState.SAIU,
})


@dataclass(frozen=True)
class StateEvidence:
    source_id: str
    evidence_class: str
    observed_at: str
    signal_type: str
    independent_message_count: int = 1
    official_operational: bool = False


def parse_state(value: str | MaritimePhysicalState) -> MaritimePhysicalState:
    if isinstance(value, MaritimePhysicalState):
        return value
    normalized = str(value).strip().upper().replace(" ", "_").replace("Á", "A").replace("Ç", "C")
    aliases = {
        "APROXIMAÇÃO": "APROXIMACAO",
        "ÁREA_PORTUÁRIA": "AREA_PORTUARIA",
        "AREA_PORTUARIA": "AREA_PORTUARIA",
    }
    normalized = aliases.get(str(value).strip().upper(), normalized)
    try:
        return MaritimePhysicalState[normalized]
    except KeyError as exc:
        raise ValueError(f"estado fisico maritimo invalido: {value}") from exc


def validate_state_evidence(state: str | MaritimePhysicalState, evidence: Iterable[StateEvidence]) -> None:
    target = parse_state(state)
    rows = list(evidence)
    if not rows:
        raise ValueError("estado fisico exige evidencia")

    if target in OFFICIAL_EVIDENCE_REQUIRED and not any(row.official_operational for row in rows):
        raise ValueError(f"{target.name} exige evidencia operacional oficial")

    if target in AIS_CORROBORATION_REQUIRED:
        ais_rows = [row for row in rows if row.signal_type.upper().startswith("AIS")]
        if ais_rows and sum(max(1, row.independent_message_count) for row in ais_rows) < 2:
            raise ValueError(f"{target.name} nao pode ser confirmado por uma unica mensagem AIS")


def validate_transition(previous: str | MaritimePhysicalState, current: str | MaritimePhysicalState) -> None:
    before = parse_state(previous)
    after = parse_state(current)
    if after < before:
        raise ValueError(f"regressao fisica bloqueada: {before.name}->{after.name}")


def canonical_state_order() -> list[str]:
    return [state.name for state in MaritimePhysicalState]
