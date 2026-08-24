from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LinearTrend:
    intercept: float
    slope: float

    def predict(self, x: float) -> float:
        return self.intercept + self.slope * x


def moving_average(values: Sequence[float], window: int = 5) -> float:
    if window <= 0:
        raise ValueError("window deve ser positivo")
    if len(values) < window:
        raise ValueError("historico insuficiente para a janela")
    tail = values[-window:]
    return sum(tail) / window


def fit_linear_trend(values: Sequence[float]) -> LinearTrend:
    if len(values) < 2:
        raise ValueError("ao menos dois pontos sao necessarios")
    n = len(values)
    xs = [float(i) for i in range(n)]
    mean_x = sum(xs) / n
    mean_y = sum(float(v) for v in values) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return LinearTrend(mean_y, 0.0)
    slope = sum((x - mean_x) * (float(y) - mean_y) for x, y in zip(xs, values)) / denominator
    intercept = mean_y - slope * mean_x
    return LinearTrend(intercept, slope)


def next_linear_trend(values: Sequence[float]) -> float:
    trend = fit_linear_trend(values)
    return trend.predict(float(len(values)))


def same_period_last_year(history: Sequence[float], seasonal_period: int) -> float:
    if seasonal_period <= 0:
        raise ValueError("seasonal_period deve ser positivo")
    if len(history) < seasonal_period:
        raise ValueError("historico insuficiente para baseline sazonal")
    return float(history[-seasonal_period])


def seasonal_mean(history: Sequence[float], *, seasonal_period: int, years: int = 5) -> float:
    if seasonal_period <= 0 or years <= 0:
        raise ValueError("periodo e anos devem ser positivos")
    required = seasonal_period * years
    if len(history) < required:
        raise ValueError("historico insuficiente para media sazonal")
    points = [float(history[-seasonal_period * offset]) for offset in range(1, years + 1)]
    return sum(points) / len(points)


def climatology_probability(outcomes: Sequence[int]) -> float:
    if not outcomes:
        raise ValueError("outcomes vazio")
    if any(value not in {0, 1} for value in outcomes):
        raise ValueError("outcomes devem ser binarios")
    return sum(outcomes) / len(outcomes)


def deterministic_balance(
    *,
    opening_stock: float,
    production: float,
    inflows: float = 0.0,
    crush: float = 0.0,
    exports: float = 0.0,
    other_outflows: float = 0.0,
) -> float:
    values = (opening_stock, production, inflows, crush, exports, other_outflows)
    if any(value < 0 for value in values):
        raise ValueError("componentes do balanco nao podem ser negativos")
    return opening_stock + production + inflows - crush - exports - other_outflows


def deterministic_export_parity(
    *,
    gross_export_value_brl_per_sc: float,
    port_cost_brl_per_sc: float,
    transport_brl_per_sc: float,
    commercial_cost_brl_per_sc: float,
) -> float:
    if min(gross_export_value_brl_per_sc, port_cost_brl_per_sc, transport_brl_per_sc, commercial_cost_brl_per_sc) < 0:
        raise ValueError("componentes da paridade nao podem ser negativos")
    return gross_export_value_brl_per_sc - port_cost_brl_per_sc - transport_brl_per_sc - commercial_cost_brl_per_sc
