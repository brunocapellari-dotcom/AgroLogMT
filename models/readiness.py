from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable


@dataclass(frozen=True)
class GateFailure:
    code: str
    message: str


@dataclass(frozen=True)
class GateResult:
    ready: bool
    failures: tuple[GateFailure, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "failures": [failure.__dict__ for failure in self.failures],
        }


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _history_years(meta: dict[str, Any]) -> float | None:
    explicit = meta.get("history_years")
    if explicit is not None:
        return float(explicit)
    first = _parse_iso_date(meta.get("first_reference_date"))
    last = _parse_iso_date(meta.get("last_reference_date"))
    if first is None or last is None or last < first:
        return None
    return (last - first).days / 365.2425


def evaluate_table_requirement(table_name: str, meta: dict[str, Any] | None, requirement: dict[str, Any]) -> GateResult:
    failures: list[GateFailure] = []
    if not meta or not bool(meta.get("exists")):
        failures.append(GateFailure("TABLE_MISSING", f"{table_name}: tabela ausente"))
        return GateResult(False, tuple(failures))

    if meta.get("qa_status") != "pass":
        failures.append(GateFailure("QA_NOT_PASS", f"{table_name}: qa_status deve ser pass"))
    if requirement.get("point_in_time_required", True) and not bool(meta.get("point_in_time_ready")):
        failures.append(GateFailure("POINT_IN_TIME_MISSING", f"{table_name}: metadados point-in-time incompletos"))
    if requirement.get("canonical_geo_required") and not bool(meta.get("canonical_geo_ready")):
        failures.append(GateFailure("CANONICAL_GEO_MISSING", f"{table_name}: geografia canonica ausente"))

    min_rows = requirement.get("minimum_rows")
    if min_rows is not None and int(meta.get("rows") or 0) < int(min_rows):
        failures.append(GateFailure("INSUFFICIENT_ROWS", f"{table_name}: linhas abaixo do minimo {min_rows}"))

    min_years = requirement.get("minimum_history_years")
    if min_years is not None:
        observed_years = _history_years(meta)
        if observed_years is None or observed_years + 1e-9 < float(min_years):
            failures.append(GateFailure("INSUFFICIENT_HISTORY_YEARS", f"{table_name}: historico abaixo de {min_years} anos"))

    min_seasons = requirement.get("minimum_history_seasons")
    if min_seasons is not None and int(meta.get("history_seasons") or 0) < int(min_seasons):
        failures.append(GateFailure("INSUFFICIENT_HISTORY_SEASONS", f"{table_name}: safras abaixo de {min_seasons}"))

    min_snapshots = requirement.get("minimum_history_snapshots")
    if min_snapshots is not None and int(meta.get("snapshots") or 0) < int(min_snapshots):
        failures.append(GateFailure("INSUFFICIENT_SNAPSHOTS", f"{table_name}: snapshots abaixo de {min_snapshots}"))

    return GateResult(not failures, tuple(failures))


def evaluate_block(block: dict[str, Any], inventory: dict[str, dict[str, Any]]) -> GateResult:
    failures: list[GateFailure] = []
    common = {
        "point_in_time_required": True,
        "canonical_geo_required": block.get("block_id") in {"production", "storage", "commercialization", "climate"},
        "minimum_history_years": block.get("minimum_history_years"),
        "minimum_history_seasons": block.get("minimum_history_seasons"),
        "minimum_history_snapshots": block.get("minimum_history_snapshots"),
    }

    for table in block.get("tables_all", []):
        result = evaluate_table_requirement(table, inventory.get(table), common)
        failures.extend(result.failures)

    alternatives = list(block.get("tables_any", []))
    if alternatives:
        alternative_results = [evaluate_table_requirement(table, inventory.get(table), common) for table in alternatives]
        if not any(result.ready for result in alternative_results):
            failures.append(GateFailure(
                "NO_ALTERNATIVE_TABLE_READY",
                f"{block.get('block_id')}: nenhuma tabela alternativa esta pronta: {', '.join(alternatives)}",
            ))

    return GateResult(not failures, tuple(failures))


def evaluate_datamart(contract: dict[str, Any], inventory: dict[str, dict[str, Any]]) -> GateResult:
    failures: list[GateFailure] = []
    for block in contract.get("blocks", []):
        if not block.get("required_for_v1"):
            continue
        result = evaluate_block(block, inventory)
        failures.extend(result.failures)
    return GateResult(not failures, tuple(failures))


def evaluate_model_contract(
    model_contract: dict[str, Any],
    *,
    available_metrics: Iterable[str],
    history_years: float | None = None,
    history_seasons: int | None = None,
    history_days: int | None = None,
    point_in_time_ready: bool,
    baseline_ready: bool,
) -> GateResult:
    metrics = set(available_metrics)
    failures: list[GateFailure] = []

    target = model_contract.get("target_metric")
    if target and target not in metrics and target not in {"estoque_final", "capacidade_pagamento_interior"}:
        failures.append(GateFailure("TARGET_MISSING", f"target ausente: {target}"))

    required_features = set(model_contract.get("features", []))
    missing_features = sorted(feature for feature in required_features if feature not in metrics and not feature.startswith(("estoque_", "entradas", "outras_saidas", "custos_", "backhaul_signal", "congestionamento", "capacidade_intermodal", "crop_stage", "forecast_ensemble")))
    if missing_features:
        failures.append(GateFailure("FEATURES_MISSING", f"features ausentes: {', '.join(missing_features)}"))

    minimum = model_contract.get("minimum_history", {})
    if "years" in minimum and (history_years is None or history_years + 1e-9 < float(minimum["years"])):
        failures.append(GateFailure("INSUFFICIENT_HISTORY_YEARS", f"modelo exige {minimum['years']} anos"))
    if "seasons" in minimum and (history_seasons is None or history_seasons < int(minimum["seasons"])):
        failures.append(GateFailure("INSUFFICIENT_HISTORY_SEASONS", f"modelo exige {minimum['seasons']} safras"))
    if "days" in minimum and (history_days is None or history_days < int(minimum["days"])):
        failures.append(GateFailure("INSUFFICIENT_HISTORY_DAYS", f"modelo exige {minimum['days']} dias"))

    if not point_in_time_ready:
        failures.append(GateFailure("POINT_IN_TIME_MISSING", "dataset do modelo ainda nao e point-in-time seguro"))
    if not baseline_ready:
        failures.append(GateFailure("BASELINE_MISSING", "baseline obrigatorio ainda nao executavel"))

    return GateResult(not failures, tuple(failures))
