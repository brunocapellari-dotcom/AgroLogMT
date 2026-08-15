-- Evidência versionada de atualização do GDELT: data máxima de evento
-- dentro das partições dos últimos dias. Execução real (não dry-run) em
-- 2026-08-15 retornou max_date = 20260815 (o próprio dia da consulta),
-- confirmando que a partição do dia corrente já está populada. Ver
-- achado de atualização em ../README.md — esta consulta não mede o
-- intervalo de ~15 min entre updates declarado pela documentação do
-- GDELT Project, apenas a presença de dados do dia corrente.
SELECT
  MAX(SQLDATE) AS max_date,
  COUNT(*) AS n
FROM `gdelt-bq.gdeltv2.events_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP('2026-08-13');
