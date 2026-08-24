-- Validação pós-carga: CONAB Armazéns
-- Substitua PROJECT_ID pelo projeto GCP real antes da execução.

-- 1) snapshots e contagens
SELECT
  snapshot_id,
  MIN(data_referencia) AS data_referencia,
  MIN(data_coleta) AS primeira_coleta,
  MAX(data_coleta) AS ultima_coleta,
  COUNT(*) AS registros,
  COUNT(DISTINCT record_id) AS registros_distintos,
  COUNT(DISTINCT warehouse_id) AS unidades_distintas,
  SUM(COALESCE(capacidade_estatica_t, 0)) AS capacidade_estatica_t
FROM `PROJECT_ID.logistica.armazens_conab`
GROUP BY snapshot_id
ORDER BY ultima_coleta DESC;

-- 2) idempotência dentro do snapshot
SELECT snapshot_id, record_id, COUNT(*) AS n
FROM `PROJECT_ID.logistica.armazens_conab`
GROUP BY snapshot_id, record_id
HAVING COUNT(*) > 1;

-- 3) qualidade geográfica
SELECT
  COUNT(*) AS registros,
  COUNTIF(uf IS NULL OR LENGTH(uf) != 2) AS uf_invalida,
  COUNTIF(municipio IS NULL OR TRIM(municipio) = '') AS municipio_ausente,
  COUNTIF(latitude IS NOT NULL AND NOT BETWEEN(latitude, -90, 90)) AS latitude_invalida,
  COUNTIF(longitude IS NOT NULL AND NOT BETWEEN(longitude, -180, 180)) AS longitude_invalida
FROM `PROJECT_ID.logistica.v_armazens_conab_latest`;

-- 4) capacidade por UF no snapshot mais recente
SELECT
  uf,
  COUNT(DISTINCT warehouse_id) AS unidades,
  SUM(COALESCE(capacidade_estatica_t, 0)) AS capacidade_estatica_t,
  AVG(quality_score) AS quality_score_medio
FROM `PROJECT_ID.logistica.v_armazens_conab_latest`
GROUP BY uf
ORDER BY capacidade_estatica_t DESC;

-- 5) Mato Grosso por município
SELECT
  municipio,
  COUNT(DISTINCT warehouse_id) AS unidades,
  SUM(COALESCE(capacidade_estatica_t, 0)) AS capacidade_estatica_t
FROM `PROJECT_ID.logistica.v_armazens_conab_latest`
WHERE uf = 'MT'
GROUP BY municipio
ORDER BY capacidade_estatica_t DESC;

-- 6) auditoria operacional
SELECT *
FROM `PROJECT_ID.agrolog_ops.domain_load_runs`
WHERE source_id = 'conab_armazens_cadastrados'
ORDER BY finished_at DESC
LIMIT 100;
