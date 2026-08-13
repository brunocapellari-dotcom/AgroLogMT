-- Carregue o CSV do lote em `SEU_PROJETO.logistica._stage_armazens_snapshot_membros` e execute este MERGE.
MERGE `SEU_PROJETO.logistica.armazens_snapshot_membros` T
USING `SEU_PROJETO.logistica._stage_armazens_snapshot_membros` S
ON T.hash_registro = S.hash_registro
WHEN NOT MATCHED THEN
  INSERT (`identificacao_armazem`, `hash_chave_armazem`, `hash_versao_armazem`, `uf`, `cod_ibge`, `snapshot_id`, `data_snapshot`, `snapshot_basis`, `data_coleta`, `data_publicacao`, `data_referencia`, `competencia`, `coleta_em_utc`, `source_id`, `source_url`, `arquivo_origem`, `hash_arquivo_sha256`, `hash_registro`, `hash_chave_natural`, `status_snapshot`) VALUES (S.`identificacao_armazem`, S.`hash_chave_armazem`, S.`hash_versao_armazem`, S.`uf`, S.`cod_ibge`, S.`snapshot_id`, S.`data_snapshot`, S.`snapshot_basis`, S.`data_coleta`, S.`data_publicacao`, S.`data_referencia`, S.`competencia`, S.`coleta_em_utc`, S.`source_id`, S.`source_url`, S.`arquivo_origem`, S.`hash_arquivo_sha256`, S.`hash_registro`, S.`hash_chave_natural`, S.`status_snapshot`);
