-- Eventos GDELT v2 geolocalizados em Mato Grosso, Brasil, em janela
-- fechada cobrindo 01-15/08/2026 inclusive (limite superior exclusivo em
-- 2026-08-16). Janela fechada é deliberada: uma versão anterior desta
-- query usava só limite inferior, com custo crescente a cada execução
-- futura — ver achado corrigido em ../README.md.
-- Executada em gdelt-bq (location: US), leitura pública.
-- Filtra por _PARTITIONTIME (poda de partição) para evitar full scan de
-- events_partitioned. Nota: essa poda só funciona em consulta direta ao
-- dataset em US — a feature de global queries (Preview) não permite
-- referenciar pseudocolunas como _PARTITIONTIME (a consulta, tal como
-- está, falharia via global query); uma reescrita sem esse filtro seria
-- necessária e exigiria full scan remoto, custando muito mais.
-- Bytes estimados (dry-run, exatamente esta query, janela fechada): ~138 MB.
-- Resultado real (2026-08-15): eventos com ActionGeo_Fullname contendo
-- "Mato Grosso", confirmando cobertura, mas com nomes de ator
-- frequentemente genéricos (ex. "COMPANIES", "AUTHORITIES") — conteúdo
-- semântico é inferido pelo pipeline do GDELT, não observação direta;
-- ver limitações de qualidade em ../README.md.
SELECT
  SQLDATE,
  Actor1Name,
  Actor2Name,
  EventCode,
  GoldsteinScale,
  ActionGeo_Fullname
FROM `gdelt-bq.gdeltv2.events_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP('2026-08-01')
  AND _PARTITIONTIME < TIMESTAMP('2026-08-16')
  AND ActionGeo_CountryCode = 'BR'
  AND ActionGeo_Fullname LIKE '%Mato Grosso%';
