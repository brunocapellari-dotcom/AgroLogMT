# N6 — Estado de Execução

Este documento registra o estado operacional do caminho crítico N6. `docs/N6_PROGRAM.md` continua sendo a fonte canônica dos critérios científicos; `docs/BACKLOG.md` continua sendo o backlog geral. Este arquivo registra somente execução, gates e evidências.

## Regra de estado

- **DONE**: implementado e validado no nível correspondente sem depender de evidência externa ausente.
- **READY**: código/contrato pronto; execução depende do ambiente produtivo ou de gate anterior.
- **BLOCKED-GCP**: exige credenciais/execução no GCP real e não pode ser declarado concluído por revisão de código.
- **GATED**: não deve entrar em produção antes de P0/P1, embora contrato/testes/PoCs possam avançar.

## Ciclo N6-01 — núcleo e primeira vertical

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
| 13 | CONAB Safra point-in-time | DONE no parser/probe; GATED para produção | adapter GOV.BR + XLSX reader + parser produto×UF/BR + live probe + testes |
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

## CONAB Safra — PoC vivo aprovado

A fonte `conab_safra_graos_xlsx` permanece `enabled=false` em produção até P0/P1. Fora da produção, porém, o parser foi testado contra o XLSX oficial vivo do 11º Levantamento da safra 2025/26.

### Componentes implementados

- adapter GOV.BR que localiza o levantamento e o anexo XLSX oficiais sem hardcode mensal;
- leitor XLSX próprio em ZIP/XML, sem Excel/LibreOffice e sem avaliação de fórmulas;
- parser de domínio de `produto × UF` e `Brasil - Total por Produto`;
- preservação das duas safras publicadas no workbook como `previous` e `current` dentro do mesmo vintage;
- área em mil ha, produtividade em kg/ha, produção em mil t e variações publicadas;
- IDs canônicos iniciais de produtos;
- quality gate de não-negatividade e identidade área × produtividade ≈ produção;
- tolerância de QA para arredondamento publicado em linhas de pequeno volume, evitando falso positivo percentual;
- workflow de live probe que consulta a fonte real sem versionar o workbook no GitHub.

### Evidência do probe em 24/08/2026

- arquivo oficial observado: XLSX do 11º Levantamento 2025/26;
- tamanho: 986.085 bytes;
- 76 planilhas;
- 2.184 registros extraídos considerando `previous` + `current`;
- 1.092 registros `current`;
- 28 geografias canônicas (27 UFs + Brasil);
- 59 IDs de produto no conjunto corrente;
- após ajustar o quality gate para a precisão publicada do workbook, **0 registros correntes ficaram com inconsistência material** de área × produtividade × produção.

O primeiro probe havia marcado 46 linhas pequenas por erro percentual aparente provocado pelo arredondamento de área e produção. A revisão do gate manteve o limiar percentual, mas acrescentou tolerância absoluta material; o live probe seguinte passou com zero flags correntes.

Controles sentinela aprovados no workbook real:

| Geo | Produto | Safra | Área mil ha | Produtividade kg/ha | Produção mil t | QA |
|---|---|---:|---:|---:|---:|---|
| MT | soja | 25/26 | 13.006,2 | 3.969 | 51.621,6 | score 1,0 |
| MT | milho 2ª safra | 25/26 | 7.546,6 | 7.604 | 57.384,3 | score 1,0 |
| MT | algodão pluma | 25/26 | 1.393,3 | 2.023,332 | 2.819,1 | score 1,0 |
| BR | soja | 25/26 | 48.610,3 | 3.712,455 | 180.463,5 | score 1,0 |

Os valores acima são leitura da publicação corrente e não substituem o armazenamento de cada publicação/vintage histórico.

## IMEA

O trabalho pré-produção preservado em `bootstrap/v3-conab-imea` foi recuperado como insumo de migração, não como segunda fonte canônica. O contrato atual define snapshots, indicadores confiáveis, custo de produção, Oferta & Demanda e Estimativas. O merge bruto do branch histórico é proibido; parsers/QA úteis devem ser migrados incrementalmente.

## Comex Stat

O contrato atual separa NCM de Município-SH4, preserva semântica geográfica e proíbe converter URF automaticamente em porto. A ingestão de arquivos anuais deverá ser streaming/chunked; o coletor genérico bytes-in-memory não deve ser usado para microdados grandes.

## Clima e hidrologia

O contrato inicial separa observação ANA, produto modelado NASA POWER e reanálise ERA5/AgERA5. Forecast/reanálise/estação não podem ser misturados sem subtype, e backtests devem preservar initialization/availability quando aplicável.

## Regra de materialização do Data Mart Soja MT

`docs/SOY_MT_DATAMART.md` continua sendo o contrato. A tabela/view integrada só deve ser materializada quando as fontes necessárias tiverem tabelas canônicas e QA aprovado. Antes disso, não criar SQL fictício nem tabelas vazias apenas para demonstrar arquitetura.

## Próximo gate após P0/P1

A expansão produtiva passa a seguir esta ordem: CONAB Safra → migração IMEA → Comex Stat → clima/ANA → Data Mart Soja MT → treino dos seis modelos iniciais → backtests point-in-time → relatório N6 integrado → auditoria de promoção.
