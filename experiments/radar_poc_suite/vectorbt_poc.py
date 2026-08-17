from __future__ import annotations

import math


def main() -> int:
    try:
        import numpy as np
        import pandas as pd
        import vectorbt as vbt
    except ImportError as exc:
        raise SystemExit(
            "VectorBT não instalado. Use o ambiente isolado e requirements-optional.txt."
        ) from exc

    rng = np.random.default_rng(42)
    index = pd.date_range("2025-01-01", periods=240, freq="D")
    trend = np.linspace(0.0, 12.0, len(index))
    seasonality = np.sin(np.arange(len(index)) / 11.0) * 2.5
    noise = rng.normal(0.0, 0.9, len(index))
    pressure_index = pd.Series(50.0 + trend + seasonality + noise, index=index)

    fast = vbt.MA.run(pressure_index, 5).ma
    slow = vbt.MA.run(pressure_index, 20).ma

    # O sinal do dia T usa somente informação disponível até T-1.
    signal = (fast > slow).shift(1).fillna(False)

    # O futuro é usado apenas como target de avaliação, nunca na geração do sinal.
    horizon_days = 7
    future_change = pressure_index.shift(-horizon_days) - pressure_index
    target_up = future_change > 0

    valid = future_change.notna()
    predicted = signal[valid].astype(bool)
    actual = target_up[valid].astype(bool)
    accuracy = float((predicted == actual).mean())
    coverage = float(predicted.mean())

    if not (0.0 <= accuracy <= 1.0) or not math.isfinite(accuracy):
        raise RuntimeError("Métrica inválida no PoC.")

    print("AgroLog MT — VectorBT point-in-time PoC")
    print(f"observations={int(valid.sum())}")
    print(f"horizon_days={horizon_days}")
    print(f"accuracy={accuracy:.3f}")
    print(f"signal_coverage={coverage:.3f}")
    print("look_ahead_control=signal shifted by 1 day; future only used as evaluation target")
    print("data=synthetic; result has no market meaning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
