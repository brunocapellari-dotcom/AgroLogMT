from __future__ import annotations

import math
from typing import Any


def _finite_nonnegative(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def _percentile(value: float | None, name: str) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return number


def producer_selling_conditions_vector(
    *,
    physical_price_percentile: float | None,
    basis_percentile: float | None,
    export_parity_spread_brl_sc: float | None,
    commercialization_delta_pp: float | None,
) -> dict[str, Any]:
    """Return an evidence vector without inventing an uncalibrated composite score.

    A positive/negative parity spread and commercialization delta are preserved as
    observed/derived components. Their economic interpretation belongs to an
    audited methodology, not to this low-level function.
    """
    price = _percentile(physical_price_percentile, "physical_price_percentile")
    basis = _percentile(basis_percentile, "basis_percentile")

    parity = None if export_parity_spread_brl_sc is None else float(export_parity_spread_brl_sc)
    commercialization = (
        None if commercialization_delta_pp is None else float(commercialization_delta_pp)
    )
    for name, value in (
        ("export_parity_spread_brl_sc", parity),
        ("commercialization_delta_pp", commercialization),
    ):
        if value is not None and not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

    components = {
        "physical_price_percentile": price,
        "basis_percentile": basis,
        "export_parity_spread_brl_sc": parity,
        "commercialization_delta_pp": commercialization,
    }
    missing = sorted(name for name, value in components.items() if value is None)
    return {
        "status": "VECTOR_READY" if not missing else "DATA_GATED",
        "components": components,
        "missing_components": missing,
        "composite_score": None,
        "evidence_class": "inferido" if not missing else None,
        "flags": ["uncalibrated_composite_prohibited"],
    }


def demand_30d_evidence_vector(
    *,
    export_programmed_t: float | None,
    export_realized_trailing_30d_t: float | None,
    industrial_demand_reference_t: float | None,
    domestic_flow_trailing_30d_t: float | None,
) -> dict[str, Any]:
    """Preserve demand evidence channels without treating unlike evidence as additive.

    Programmed line-up is not realized export. Industrial demand may use another
    reference period. The vector is therefore descriptive until a point-in-time
    forecast model explicitly defines transformations and backtests them.
    """
    components = {
        "export_programmed_t": _finite_nonnegative(
            export_programmed_t, "export_programmed_t"
        ),
        "export_realized_trailing_30d_t": _finite_nonnegative(
            export_realized_trailing_30d_t, "export_realized_trailing_30d_t"
        ),
        "industrial_demand_reference_t": _finite_nonnegative(
            industrial_demand_reference_t, "industrial_demand_reference_t"
        ),
        "domestic_flow_trailing_30d_t": _finite_nonnegative(
            domestic_flow_trailing_30d_t, "domestic_flow_trailing_30d_t"
        ),
    }
    missing = sorted(name for name, value in components.items() if value is None)
    return {
        "status": "VECTOR_READY" if not missing else "DATA_GATED",
        "components": components,
        "missing_components": missing,
        "aggregate_demand_t": None,
        "forecast_30d_t": None,
        "flags": [
            "programmed_is_not_realized",
            "mixed_reference_periods_not_additive",
            "forecast_requires_point_in_time_backtest",
        ],
    }
