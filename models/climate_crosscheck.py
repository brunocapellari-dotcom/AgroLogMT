from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class ClimateCrosscheck:
    n: int
    mean_bias: float
    mae: float
    rmse: float
    correlation: float | None

    def to_dict(self):
        return asdict(self)


def compare(reference: Iterable[float], candidate: Iterable[float]) -> ClimateCrosscheck:
    pairs = [(float(a), float(b)) for a, b in zip(reference, candidate)]
    if not pairs:
        raise ValueError("no paired observations")
    errors = [b - a for a, b in pairs]
    bias = sum(errors) / len(errors)
    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
    xs = [a for a, _ in pairs]; ys = [b for _, b in pairs]
    mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
    num = sum((x-mx)*(y-my) for x,y in pairs)
    denx = math.sqrt(sum((x-mx)**2 for x in xs)); deny = math.sqrt(sum((y-my)**2 for y in ys))
    corr = None if not denx or not deny else num / (denx * deny)
    return ClimateCrosscheck(len(pairs), bias, mae, rmse, corr)
