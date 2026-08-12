---
tipo: pipeline
fonte: CONAB
status: pronto_para_claude_code
prioridade: P0
ultima_revisao: 2026-08-12
---

# Pipeline - CONAB Armazens

[[CONAB]] → download oficial → GCS raw imutável → staging BigQuery → DQ → comparação de snapshot → MERGE → `logistica.armazens` → views → indicadores/relatórios.

## Contrato técnico

- manifesto: `sources/conab/armazens/source_manifest.yaml`
- schema: `sources/conab/armazens/schema.json`
- instruções: `sources/conab/armazens/CLAUDE_CODE_INSTRUCTIONS.md`

## Regras

- hash SHA-256 do raw;
- `snapshot_id` e `ingestion_run_id`;
- ausência no snapshot atual não exclui cadastro;
- registrar novos, alterados, inalterados, ausentes e erros;
- reexecução do mesmo arquivo deve ser idempotente;
- somente marcar integrado/produção após carga real, logs, DQ e consulta validada.

## Próxima ação

Claude Code executar o pipeline no ambiente real do Google Cloud, seguindo os contratos do repositório.
