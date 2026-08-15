-- Estações NOAA GSOD dentro de uma bounding box retangular que cobre
-- Mato Grosso, Brasil. A bounding box não é o polígono real do estado
-- (pode incluir estações de estados/países vizinhos); ver ressalva em
-- ../README.md.
-- Executada em bigquery-public-data (location: US), leitura pública, sem
-- autenticação especial além do projeto padrão do usuário.
-- Bytes estimados (dry-run): ~2,3 MB processados (tabela `stations` inteira).
-- Resultado real (2026-08-15): >50 estações na região, incluindo CUIABA
-- (usaf=833610) e MARECHAL RONDON / aeroporto de Cuiabá (usaf=833620).
SELECT
  usaf,
  wban,
  name,
  lat,
  lon,
  elev,
  begin,
  `end`
FROM `bigquery-public-data.noaa_gsod.stations`
WHERE country = 'BR'
  AND lat BETWEEN -18 AND -7
  AND lon BETWEEN -61 AND -50
ORDER BY name;
