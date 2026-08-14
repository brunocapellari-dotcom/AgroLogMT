from __future__ import annotations

import os
import re
from dataclasses import dataclass


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


class ConfigurationError(RuntimeError):
    """Raised when mandatory runtime configuration is missing or unsafe."""


@dataclass(frozen=True)
class Settings:
    project_id: str
    bq_location: str
    dataset: str = "logistica"
    armazens_view: str = "vw_armazens_atuais"
    max_bytes_billed: int = 100_000_000

    @property
    def armazens_table_ref(self) -> str:
        return f"{self.project_id}.{self.dataset}.{self.armazens_view}"


def _safe_identifier(value: str, field: str) -> str:
    if not value or not _IDENTIFIER_RE.fullmatch(value):
        raise ConfigurationError(f"Configuração inválida para {field}.")
    return value


def load_settings() -> Settings:
    project_id = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
    bq_location = (os.getenv("BQ_LOCATION") or "").strip()
    dataset = (os.getenv("AGROLOG_BQ_DATASET") or "logistica").strip()
    armazens_view = (os.getenv("AGROLOG_ARMAZENS_VIEW") or "vw_armazens_atuais").strip()
    max_bytes_raw = (os.getenv("AGROLOG_GATEWAY_MAX_BYTES_BILLED") or "100000000").strip()

    if not project_id:
        raise ConfigurationError("GOOGLE_CLOUD_PROJECT não configurado.")
    if not _PROJECT_RE.fullmatch(project_id):
        raise ConfigurationError("GOOGLE_CLOUD_PROJECT possui formato inválido.")
    if not bq_location:
        raise ConfigurationError("BQ_LOCATION não configurado.")

    dataset = _safe_identifier(dataset, "AGROLOG_BQ_DATASET")
    armazens_view = _safe_identifier(armazens_view, "AGROLOG_ARMAZENS_VIEW")

    try:
        max_bytes_billed = int(max_bytes_raw)
    except ValueError as exc:
        raise ConfigurationError("AGROLOG_GATEWAY_MAX_BYTES_BILLED deve ser inteiro.") from exc
    if max_bytes_billed <= 0:
        raise ConfigurationError("AGROLOG_GATEWAY_MAX_BYTES_BILLED deve ser positivo.")

    return Settings(
        project_id=project_id,
        bq_location=bq_location,
        dataset=dataset,
        armazens_view=armazens_view,
        max_bytes_billed=max_bytes_billed,
    )
