# N6 — Política de Promoção de Modelos

## Princípio

O AgroLog MT não promove um modelo porque ele é sofisticado ou porque teve boa média em um backtest isolado. Promoção exige ganho contra baseline, estabilidade temporal, ausência de leakage e coerência operacional.

## Modelos de regressão

O gate inicial em `models/promotion.py` exige, por padrão:

- dataset readiness aprovado;
- point-in-time verificado;
- leakage checks aprovados;
- pelo menos 5 folds fora da amostra;
- melhora mínima de 3% em MAE contra baseline;
- melhora mínima de 3% em RMSE contra baseline;
- ganho positivo em pelo menos 60% dos folds;
- pior fold não pode degradar mais de 20% contra baseline.

Esses valores são gates iniciais conservadores e podem ser endurecidos por modelo após evidência real. Nunca devem ser relaxados apenas para permitir promoção.

## Modelos probabilísticos

Risco agroclimático e outros modelos probabilísticos precisam adicionalmente:

- Brier Skill Score positivo e acima do threshold;
- estabilidade por folds/regiões/safras;
- erro de calibração dentro do limite;
- análise de reliability/calibration e, quando aplicável, discriminação.

Probabilidade bem ranqueada mas mal calibrada não deve ser apresentada como probabilidade operacional.

## Harness sintético

`scripts/run_n6_synthetic_backtest.py` existe apenas para provar que métricas, estabilidade e gate de promoção estão tecnicamente conectados. O resultado desse script nunca pode ser citado como desempenho real de YIELD, EXPORT30, FREIGHT-PRESSURE, AGROCLIMATE-RISK ou qualquer outro modelo.

## Promoção final N6

`promotion_candidate` ainda não equivale a `production_validated`. Antes de produção é necessária auditoria independente cobrindo:

1. dataset e proveniência;
2. definição do target;
3. cortes point-in-time;
4. baseline;
5. regime/safra/região;
6. estabilidade;
7. interpretação econômica/operacional;
8. sensibilidade a revisões de fonte;
9. limites de uso;
10. monitoramento pós-deploy e gatilho de rollback.
