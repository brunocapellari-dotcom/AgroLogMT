# CONAB Armazéns — validação BigQuery real — 2026-08-13

## Resultado

- Testes locais: **APROVADO**.
- Primeira carga BigQuery: **APROVADO**.
- Idempotência analítica: **COMPROVADA**.
- Contadores de movimento: **COMPROVADOS após correção mínima descoberta no teste real**.

## Execuções

| Execução | Armazéns | Snapshots | Membros | novos | alterados | inalterados | ausentes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 0 | 0 | 0 | — | — | — | — |
| 1ª carga | 18.807 | 1 | 18.807 | 18.807 | 0 | 0 | 0 |
| 2ª carga, antes da correção do log | 18.807 | 1 | 18.807 | 18.807* | 0 | 0 | 0 |
| 3ª carga, código corrigido | 18.807 | 1 | 18.807 | 0 | 0 | 18.807 | 0 |

\* Os dados analíticos já permaneceram sem duplicação na segunda execução. O problema estava somente no cálculo do log de movimento.

## Bug descoberto e corrigido

`load_historical.py` calculava movimentos apenas com os snapshots presentes no pacote histórico. Como o pacote do piloto possuía um único snapshot, a segunda carga era registrada incorretamente como 18.807 novos.

A correção passou a usar o contexto do último snapshot `COMPLETO` já persistido antes dos MERGEs, reutilizando `latest_complete_armazens_context()` e mantendo `armazens_movement_counts()` como regra única.

Depois da correção, os cinco testes locais foram repetidos e a terceira carga real retornou `novos=0`, `alterados=0`, `inalterados=18807` e `ausentes_no_snapshot_atual=0`.

## Estado consolidado

- 18.807 armazéns;
- 1 snapshot `COMPLETO`;
- 18.807 membros de snapshot;
- Mato Grosso: 2.917 armazéns, 107 municípios e 58.368.190 t de capacidade estática;
- nenhuma duplicação analítica após três execuções;
- a linha incorreta da segunda execução foi preservada como histórico real.

## Limite da aprovação

A aprovação cobre a carga histórica de **CONAB Armazéns** no BigQuery real e sua idempotência. Coleta HTTP ao vivo, RAW em Cloud Storage, Cloud Run Job, Scheduler e demais famílias CONAB permanecem etapas posteriores.
