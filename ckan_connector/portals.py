from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortalConfig:
    """Identidade de um portal CKAN oficial já validado.

    Guarda apenas o necessário para descoberta/download genéricos (Issue #19).
    Regras específicas de parsing/carga de cada fonte (schema, mapeamento de
    colunas, destino no BigQuery) permanecem fora deste módulo, em código
    próprio de cada fonte.
    """

    name: str
    base_url: str
    notes: str = ""


KNOWN_PORTALS: dict[str, PortalConfig] = {
    "aneel": PortalConfig(
        name="aneel",
        base_url="https://dadosabertos.aneel.gov.br",
        notes="ANEEL Dados Abertos — API CKAN pública, validada em 2026-08-15.",
    ),
    "antt": PortalConfig(
        name="antt",
        base_url="https://dados.antt.gov.br",
        notes="ANTT Dados Abertos — API CKAN pública, validada em 2026-08-15.",
    ),
}
