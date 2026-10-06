-- Evidência versionada da defasagem do dataset: data mais recente
-- disponível em toda a tabela gsod2025 (todas as estações do mundo, não
-- só MT). Execução real (não dry-run) em 2026-08-15 retornou
-- max_date = 2025-08-28 — defasagem de ~1 ano em relação à data desta
-- avaliação. Ver achado de atualização em ../README.md.
SELECT
  MAX(CONCAT(year, '-', mo, '-', da)) AS max_date
FROM `bigquery-public-data.noaa_gsod.gsod2025`;
