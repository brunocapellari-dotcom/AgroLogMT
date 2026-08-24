# N6 — Feature Matrix Point-in-Time

## Objetivo

Transformar as tabelas canonicas do AgroLog MT em datasets de treino reproduziveis sem contaminar o passado com revisoes ou resultados futuros.

## Contrato

`models/feature_matrix.py` recebe registros long-form canonicos, um `cutoff`, campos de entidade e a lista de `metric_id` exigidos pelo modelo. Para cada entidade + metrica, seleciona somente a ultima observacao que realmente estava disponivel ate o cutoff.

A disponibilidade continua definida por `max(data_publicacao, data_coleta)` quando ambos existem. `data_referencia` nunca e usada como proxy de disponibilidade.

Uma entidade so entra na matriz quando todas as features obrigatorias possuem valor valido no cutoff. O processo preserva por feature:

- source_id;
- momento de disponibilidade;
- data de referencia;
- data de publicacao;
- data de coleta;
- source_hash;
- methodology_id.

## Target

`models/training_dataset.py` anexa o target em etapa separada. O target:

- nao pode existir entre as features;
- deve se referir a momento posterior ao cutoff;
- nao fornece metadados futuros para a matriz de features;
- permanece separado da provenance das features.

## Regra operacional

O primeiro treino real so deve ocorrer depois de:

1. Data Mart readiness = PASS;
2. feature contract do modelo = PASS;
3. historico minimo = PASS;
4. feature matrix point-in-time gerada;
5. baseline executado no mesmo conjunto de cortes;
6. rolling-origin/out-of-sample preparado.

Isso evita que uma boa metrica de backtest seja produzida por revisao futura, target leakage ou transformacao ajustada com informacao posterior.
