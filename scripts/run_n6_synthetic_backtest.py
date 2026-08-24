#!/usr/bin/env python3
from __future__ import annotations

import json

from models.evaluation import regression_skill, stability
from models.promotion import evaluate_regression_promotion


def main() -> int:
    # Harness sintético: prova somente encadeamento de métricas/gates.
    # Não representa desempenho real de nenhum modelo AgroLog MT.
    folds = [
        ([100, 110, 120], [101, 109, 121], [96, 106, 116]),
        ([130, 140, 150], [129, 142, 151], [125, 135, 145]),
        ([160, 170, 180], [161, 169, 181], [155, 165, 175]),
        ([190, 200, 210], [191, 199, 211], [185, 195, 205]),
        ([220, 230, 240], [221, 229, 241], [215, 225, 235]),
        ([250, 260, 270], [251, 259, 271], [245, 255, 265]),
    ]

    mae_improvements = []
    rmse_improvements = []
    for actual, model_pred, baseline_pred in folds:
        skill = regression_skill(actual, model_pred, baseline_pred)
        mae_improvements.append(skill.mae_improvement)
        rmse_improvements.append(skill.rmse_improvement)

    stable = stability(mae_improvements)
    decision = evaluate_regression_promotion(
        dataset_ready=True,
        point_in_time_verified=True,
        leakage_checks_passed=True,
        out_of_sample_folds=len(folds),
        mae_improvement=sum(mae_improvements) / len(mae_improvements),
        rmse_improvement=sum(rmse_improvements) / len(rmse_improvements),
        positive_fold_share=stable.positive_share,
        worst_fold_improvement=stable.worst_improvement,
    )

    payload = {
        "status": "PASS" if decision.promotable else "FAIL",
        "scope": "synthetic_harness_only",
        "warning": "Este resultado nao e evidencia de desempenho real de modelo.",
        "folds": len(folds),
        "mae_improvements": mae_improvements,
        "rmse_improvements": rmse_improvements,
        "stability": stable.__dict__,
        "decision": {
            "status": decision.status,
            "reasons": list(decision.reasons),
            "metrics": decision.metrics,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if decision.promotable else 1


if __name__ == "__main__":
    raise SystemExit(main())
