-- Amostra real de dados diários 2025 para a estação MARECHAL RONDON
-- (aeroporto de Cuiabá, usaf=833620).
-- Achado de atualização: o dado mais recente em toda a tabela gsod2025
-- (todas as estações) é 2025-08-28 — defasagem de ~1 ano em relação à
-- data desta avaliação (2026-08-15). Ver ../README.md.
-- Bytes estimados (dry-run, exatamente esta query): ~96 MB processados —
-- a tabela anual inteira é lida independente do filtro de estação
-- (sem particionamento por estação dentro do ano).
SELECT
  stn,
  year,
  mo,
  da,
  temp,
  prcp
FROM `bigquery-public-data.noaa_gsod.gsod2025`
WHERE stn = '833620'
ORDER BY mo, da
LIMIT 5;
