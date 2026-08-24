# N6 — Estado de Execução

Este documento registra o estado operacional do caminho crítico N6. `docs/N6_PROGRAM.md` continua sendo a fonte canônica dos critérios científicos; `docs/BACKLOG.md` continua sendo o backlog geral. Este arquivo registra somente execução, gates e evidências.

## Regra de estado

- **DONE**: implementado e validável sem depender de evidência externa ausente.
- **READY**: código/contrato pronto; execução depende do ambiente produtivo ou de gate anterior.
- **BLOCKED-GCP**: exige credenciais/execução no GCP real e não pode ser declarado concluído por revisão de código.
- **GATED**: não deve entrar em produção antes de P0/P1, embora contrato/testes possam avançar.

## Ciclo N6-01 — 15 passos

| # | Passo | Estado | Evidência/saída |
|---:|---|---|---|
| 1 | Consolidar governança CONAB/Gateway | DONE | Issues #9 e #13 atualizadas para `logistica.armazens_conab`, `v_armazens_conab_latest`, Drive RAW e `agrolog_ops` |
| 2 | Preflight do GCP real | READY / BLOCKED-GCP | `scripts/preflight_n6_gcp.sh` |
| 3 | Corrigir IAM do coletor | DONE no código / BLOCKED-GCP na aplicação | datasets `logistica`/`agrolog_ops` explícitos + `dataEditor` em dataset + `bigquery.user` para jobs |
| 4 | Redeploy do coletor com `main` atual | READY / BLOCKED-GCP | `scripts/deploy_collectors_gcloud.sh` |
| 5 | Executar CONAB Armazéns manualmente | READY / BLOCKED-GCP | `gcloud run jobs execute` com override `AGROLOG_SOURCE_ID` |
| 6 | Auditar RAW + manifesto | READY / BLOCKED-GCP | `validate_conab_n6.py` exige hash + `drive://raw_artifact_ref` e `collector_runs` |
| 7 | Auditar BigQuery tecnicamente | READY / BLOCKED-GCP | schema, partição, clustering, snapshots, auditoria e datas no validador |
| 8 | Validar conteúdo CONAB | READY / BLOCKED-GCP | geografia, capacidade, evidência, perfil MT e qualidade |
| 9 | Provar idempotência | READY / BLOCKED-GCP | segunda execução deve gerar `already_loaded` sem duplicação |
| 10 | Implantar AgroLog Gateway | READY / BLOCKED-GCP | `scripts/deploy_gateway_gcloud.sh` |
| 11 | Validar Gateway ponta a ponta | READY / BLOCKED-GCP | `scripts/validate_gateway_n6.py` compara Gateway x BigQuery |
| 12 | Fechar P0/P1 | BLOCKED-GCP | somente após PASS dos validadores e comparação OpenAI/Codex x Claude |
| 13 | CONAB Safra point-in-time | GATED, preparação avançada | adapter GOV.BR de último anexo + source spec desabilitada + `models/point_in_time.py` |
| 14 | IMEA + Comex Stat | GATED, contratos prontos | `contracts/imea_agro.v1.json`, Issue #1 migrada, `contracts/comexstat.v1.json` |
| 15 | Clima/hidrologia + Data Mart Soja MT | GATED, contrato pronto | `contracts/climate_hydrology.v1.json` + `docs/SOY_MT_DATAMART.md` |

## Comando de homologação P0/P1

Após autenticação e permissões GCP/Drive válidas:

```bash
PROJECT_ID=<projeto> bash scripts/homologate_n6_core.sh
```

O comando executa preflight, deploy do coletor, duas execuções CONAB, validação da carga/idempotência, deploy do Gateway e comparação Gateway x BigQuery. Evidências locais são gravadas em `outputs/n6-core/`, diretório ignorado pelo Git.

## Estado científico e point-in-time

`models/point_in_time.py` estabelece que disponibilidade informacional é determinada por `data_publicacao` e `data_coleta`, usando o momento conservador em que a informação realmente poderia ser conhecida. `data_referencia` não é tratada como data de disponibilidade. Revisão futura não pode contaminar backtest histórico.

## Expansões já preparadas

### CONAB Safra

O coletor possui um adapter GOV.BR que descobre o levantamento mais recente e seu XLSX oficial sem hardcode mensal. A source spec permanece `enabled=false` até P0/P1. A etapa seguinte após homologação é desenvolver o parser de domínio sobre snapshots reais preservados e registrar cada publicação/vintage.

### IMEA

O trabalho pré-produção preservado em `bootstrap/v3-conab-imea` foi recuperado como insumo de migração, não como segunda fonte canônica. O contrato atual define snapshots, indicadores confiáveis, custo de produção, Oferta & Demanda e Estimativas. O merge bruto do branch histórico é proibido; parsers/QA úteis devem ser migrados incrementalmente.

### Comex Stat

O contrato atual separa NCM de Município-SH4, preserva semântica geográfica e proíbe converter URF automaticamente em porto. A ingestão de arquivos anuais deverá ser streaming/chunked; o coletor genérico bytes-in-memory não deve ser usado para microdados grandes.

### Clima e hidrologia

O contrato inicial separa observação ANA, produto modelado NASA POWER e reanálise ERA5/AgERA5. Forecast/reanálise/estação não podem ser misturados sem subtype, e backtests devem preservar initialization/availability quando aplicável.

## Próximo gate após P0/P1

A expansão produtiva passa a seguir esta ordem: CONAB Safra → migração IMEA → Comex Stat → clima/ANA → Data Mart Soja MT → treino dos seis modelos iniciais → backtests point-in-time → relatório N6 integrado → auditoria de promoção.
