# CONAB — módulo de fonte

Este diretório documenta o estado operacional da integração CONAB no AgroLog MT.

## Código canônico

- `collector/` — coleta, parsing, QA, schemas e carga.
- `historical/` — SQLs e regras de reconstrução/carga histórica.
- `sql/validation/conab_armazens.sql` — consultas de aceite do piloto de Armazéns.

## Estado

- Armazéns — carga histórica BigQuery: **VALIDADA** em 2026-08-13.
- Armazéns — idempotência: **COMPROVADA**.
- Armazéns — coleta HTTP oficial ao vivo: **PENDENTE**.
- Demais famílias CONAB: código/histórico com validações locais; ativação real deve ser gradual.

## Documentos

- `VALIDATION_2026-08-13.md` — evidência do piloto real.
- `NEXT_STEPS.md` — sequência operacional após o piloto.
