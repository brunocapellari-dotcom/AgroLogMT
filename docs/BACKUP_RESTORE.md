# Backup e Restore — AgroLog MT

Este documento define o gate operacional de recuperação do AgroLog MT. Backup existente não significa recuperação comprovada. Um recurso só pode ser marcado como `RESTORE_VERIFIED` após drill executado, validado e registrado segundo `contracts/restore_drill.v1.schema.json`.

## 1. Objetivos

- preservar capacidade de reconstruir dados e serviços após perda, corrupção, erro operacional ou incidente;
- separar retenção/backup de restore realmente testado;
- impedir que segredo seja exportado junto com backup de dados/configuração;
- manter evidência auditável de RPO/RTO, integridade, permissões e resultado.

## 2. Escopo

### BigQuery

- tabelas canônicas, estados de collectors, manifests e tabelas curated relevantes;
- restaurar sempre em destino isolado de recovery/staging durante o drill;
- conferir schema, row count, chaves, período, snapshots/vintages e checksums/hash quando tecnicamente aplicável;
- produção não é destino de teste destrutivo.

### RAW / Drive / object storage

- validar que artefatos originais críticos podem ser recuperados preservando hash, tamanho, origem e metadados necessários;
- nunca executar macros/scripts contidos nos artefatos recuperados;
- RAW continua `UNTRUSTED_EXTERNAL` após restore e deve passar novamente pelos gates aplicáveis antes de promoção.

### GitHub / configuração

- código continua protegido por Git e histórico remoto;
- export de configuração não inclui GitHub Secrets, Secret Manager payloads, cookies, tokens ou chaves privadas;
- infraestrutura privilegiada deve ser reconstruível por scripts versionados + identidade administrativa autorizada.

### Secret Manager

- segredo não é tratado como dataset comum e não deve ser despejado em arquivos de backup;
- recuperação/rotação de segredo segue processo de segurança e IAM, não export genérico.

## 3. Evidência mínima do drill

Cada drill deve registrar:

- `drill_id`;
- ambiente e janela de execução;
- tipo de backup/fonte;
- destino isolado de restore;
- RPO e RTO observados/alvo;
- row/object count conforme natureza do ativo;
- hash/checksum quando aplicável;
- verificação de permissões;
- confirmação de que nenhum segredo foi exportado;
- referências de logs/queries/manifestos/evidências;
- resultado `PASS` ou `FAIL`.

O avaliador canônico está em `models/restore_readiness.py`.

## 4. Regras de segurança

1. Restore drill nunca sobrescreve produção por padrão.
2. Destino de recovery recebe IAM mínimo e temporário.
3. Dados `CONFIDENTIAL/RESTRICTED` permanecem com a mesma classificação após restore.
4. Segredos não entram em snapshots de dados, ZIPs operacionais, artifacts de CI ou anexos de PR.
5. Conteúdo externo restaurado não ganha confiança por ter vindo do backup.
6. Falha de integridade, permissão ou segredo bloqueia `RESTORE_VERIFIED`.
7. Após drill, recursos temporários devem ser removidos somente depois de preservar as evidências necessárias.

## 5. Cadência

- executar após mudança material de arquitetura de armazenamento/backup;
- executar após incidente relevante;
- executar periodicamente conforme criticidade do ativo;
- datasets/RAW usados no core P0/P1 devem possuir primeiro drill antes de a plataforma ser declarada plenamente operacional.

## 6. Critério de pronto

`backup_restore = PASS` no source promotion gate exige uma evidência de restore drill com:

- `status = PASS`;
- `finished_at` presente;
- validações aplicáveis aprovadas;
- `permissions = PASS`;
- `secrets_not_exported = true`;
- pelo menos uma referência de evidência recuperável.

Até isso existir no ambiente real, o estado correto é `UNVERIFIED`, mesmo que backups/snapshots estejam configurados.
