-- AgroLog MT / CONAB Collector v1.2.2
-- Substitua SEU_PROJETO pelo project_id do Google Cloud.
-- Estado atual é definido pela composição do último snapshot COMPLETO,
-- nunca pela última ocorrência histórica de cada armazém.

CREATE OR REPLACE VIEW `SEU_PROJETO.logistica.vw_armazens_atuais` AS
WITH latest AS (
  SELECT snapshot_id, data_snapshot, coleta_em_utc
  FROM `SEU_PROJETO.logistica.armazens_snapshots`
  WHERE status_snapshot = 'COMPLETO'
  QUALIFY ROW_NUMBER() OVER (
    ORDER BY coleta_em_utc DESC, data_snapshot DESC, snapshot_id DESC
  ) = 1
)
SELECT
  a.*,
  m.snapshot_id AS snapshot_id_atual,
  m.data_snapshot AS data_snapshot_atual,
  m.coleta_em_utc AS coleta_snapshot_em_utc
FROM `SEU_PROJETO.logistica.armazens_snapshot_membros` m
JOIN latest l USING (snapshot_id)
JOIN `SEU_PROJETO.logistica.armazens` a
  ON a.hash_registro = m.hash_versao_armazem;

CREATE OR REPLACE VIEW `SEU_PROJETO.logistica.vw_armazens_movimentos_ultimo_snapshot` AS
WITH ranked AS (
  SELECT snapshot_id, data_snapshot, coleta_em_utc,
         ROW_NUMBER() OVER (ORDER BY coleta_em_utc DESC, data_snapshot DESC, snapshot_id DESC) AS rn
  FROM `SEU_PROJETO.logistica.armazens_snapshots`
  WHERE status_snapshot = 'COMPLETO'
), atual AS (
  SELECT m.* FROM `SEU_PROJETO.logistica.armazens_snapshot_membros` m
  JOIN ranked r USING (snapshot_id) WHERE r.rn = 1
), anterior AS (
  SELECT m.* FROM `SEU_PROJETO.logistica.armazens_snapshot_membros` m
  JOIN ranked r USING (snapshot_id) WHERE r.rn = 2
), contexto AS (
  SELECT COUNTIF(rn = 2) > 0 AS tem_anterior FROM ranked
), movimentos AS (
  SELECT
    COALESCE(a.hash_chave_armazem, p.hash_chave_armazem) AS hash_chave_armazem,
    COALESCE(a.identificacao_armazem, p.identificacao_armazem) AS identificacao_armazem,
    p.snapshot_id AS snapshot_anterior,
    a.snapshot_id AS snapshot_atual,
    p.hash_versao_armazem AS hash_versao_anterior,
    a.hash_versao_armazem AS hash_versao_atual,
    CASE
      WHEN NOT c.tem_anterior THEN 'BASELINE'
      WHEN p.hash_chave_armazem IS NULL THEN 'NOVO'
      WHEN a.hash_chave_armazem IS NULL THEN 'REMOVIDO'
      WHEN p.hash_versao_armazem != a.hash_versao_armazem THEN 'ALTERADO'
      ELSE 'SEM_ALTERACAO'
    END AS status_movimento
  FROM atual a
  FULL OUTER JOIN anterior p USING (hash_chave_armazem)
  CROSS JOIN contexto c
)
SELECT
  m.*,
  old.uf AS uf_anterior,
  old.municipio AS municipio_anterior,
  old.capacidade_estatica_t AS capacidade_estatica_anterior_t,
  cur.uf AS uf_atual,
  cur.municipio AS municipio_atual,
  cur.capacidade_estatica_t AS capacidade_estatica_atual_t,
  cur.capacidade_estatica_t - old.capacidade_estatica_t AS variacao_capacidade_estatica_t
FROM movimentos m
LEFT JOIN `SEU_PROJETO.logistica.armazens` old ON old.hash_registro = m.hash_versao_anterior
LEFT JOIN `SEU_PROJETO.logistica.armazens` cur ON cur.hash_registro = m.hash_versao_atual;

CREATE OR REPLACE VIEW `SEU_PROJETO.logistica.vw_armazens_novos` AS
SELECT * FROM `SEU_PROJETO.logistica.vw_armazens_movimentos_ultimo_snapshot`
WHERE status_movimento='NOVO';

CREATE OR REPLACE VIEW `SEU_PROJETO.logistica.vw_armazens_removidos` AS
SELECT * FROM `SEU_PROJETO.logistica.vw_armazens_movimentos_ultimo_snapshot`
WHERE status_movimento='REMOVIDO';

CREATE OR REPLACE VIEW `SEU_PROJETO.logistica.vw_armazens_alterados` AS
SELECT * FROM `SEU_PROJETO.logistica.vw_armazens_movimentos_ultimo_snapshot`
WHERE status_movimento='ALTERADO';
