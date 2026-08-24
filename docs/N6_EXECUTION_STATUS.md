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
| 14 | IMEA + Comex Stat | DONE no código de preparação; GATED para produção | pipeline IMEA Drive autorizado e diagnóstico TLS Comex integrados em 24/08; produção depende de P0/P1 e fonte/runtime |
| 15 | Clima/hidrologia + Data Mart Soja MT | DONE parcial / GATED | ET0 Hargreaves-Samani baseline integrado; ANA/contrato climático prontos; Data Mart só após QA das fontes canônicas |
| 16 | `NEWS_SIGNAL v0.5` | DONE no contrato/writer; GATED produtor real | genealogia, idempotência, writer local/Drive e provider readback integrados; primeiro produtor deve usar fonte material homologada |

## Aceleração consolidada — 24/08/2026

Foram promovidos para `main`, após CI verde e revisão, cinco blocos que estavam maduros e fail-closed:

- PR #95 — `NEWS_SIGNAL v0.5`: genealogia, idempotência, contrato JSON Schema, writer local/Drive, provider readback e testes;
- PR #92 — inventário histórico CONAB 2010+ em paralelo e vintage registry;
- PR #93 — diagnóstico Comex TLS atual/transitório sem `verify=false`/`curl -k`;
- PR #94 — ET0 Hargreaves-Samani baseline e resumo auditável de déficit/superávit hídrico;
- PR #91 — pipeline IMEA de workbook autorizado no Drive para RAW/QA/BigQuery, registrado porém `enabled=false` por padrão.

As PRs antigas #12 e #25 foram fechadas como **superseded** para impedir retorno ao schema/view anterior de Armazéns/Gateway. A evidência real útil da #12 foi preservada como benchmark histórico nos Issues #9/#13.

## CONAB Armazéns — benchmark histórico preservado

Em 13/08/2026 houve um piloto real da arquitetura anterior de Armazéns com:

- 18.807 armazéns;
- 1 snapshot `COMPLETO`;
- 18.807 membros de snapshot;
- Mato Grosso: 2.917 armazéns, 107 municípios e 58.368.190 t;
- terceira execução: novos=0, alterados=0, inalterados=18.807, ausentes=0;
- sem duplicação analítica e sem correção manual de dados.

Esse resultado valida **escala esperada, semântica e comportamento idempotente histórico**, mas não fecha o P0 atual: o contrato corrente usa `collector/conab_armazens*` e `logistica.armazens_conab`. O trabalho restante é re-homologar equivalência no runtime/schema atual, sem repetir investigação já resolvida.

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
- workflow de live probe que consulta a fonte real sem versionar o workbook no GitHub;
- inventário histórico profundo em blocos 2010–2013, 2014–2017, 2018–2021 e 2022–2025, com registry deduplicado e preferência por timestamp oficial verificável.

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

O pipeline operacional atual está integrado à `main`: workbook autorizado por fileId de ambiente → download Drive → cópia RAW → parser/QA → loader BigQuery → manifesto/estado. A fonte permanece `enabled=false` por padrão e só pode ser ativada após P0/P1, compartilhamento explícito com a service account e QA real do workbook autorizado. Frete IMEA continua referência observada, não frete negociado/realizado.

## Comex Stat

O contrato atual separa NCM de Município-SH4, preserva semântica geográfica e proíbe converter URF automaticamente em porto. A ingestão de arquivos anuais deverá ser streaming/chunked; o coletor genérico bytes-in-memory não deve ser usado para microdados grandes. O diagnóstico de 24/08 compara domínio atual e transitório com verificação TLS obrigatória; falha de cadeia continua `unavailable`, nunca justificativa para desabilitar TLS.

## Clima e hidrologia

O contrato separa observação ANA, produto modelado NASA POWER e reanálise ERA5/AgERA5. Forecast/reanálise/estação não podem ser misturados sem subtype, e backtests devem preservar initialization/availability quando aplicável. O baseline Hargreaves-Samani usa radiação extraterrestre FAO-56 e serve apenas quando as entradas necessárias ao Penman-Monteith não estão homologadas; não substitui FAO-56 PM em produção científica quando dados confiáveis estiverem disponíveis.

## AgroLog News / `NEWS_SIGNAL`

O writer canônico v0.5 está integrado à `main`. Todo sinal deve preservar genealogia, rule/baseline version, transformação e idempotency key. Drive é persistência operacional temporária e todo write exige readback. A mera mudança de hash/arquivo **não** autoriza sinal: um produtor real deve existir por domínio/fonte com regra de materialidade explícita e evidência rastreável.

## Regra de materialização do Data Mart Soja MT

`docs/SOY_MT_DATAMART.md` continua sendo o contrato. A tabela/view integrada só deve ser materializada quando as fontes necessárias tiverem tabelas canônicas e QA aprovado. Antes disso, não criar SQL fictício nem tabelas vazias apenas para demonstrar arquitetura.

## Próximo gate após P0/P1

A expansão produtiva passa a seguir esta ordem: CONAB Safra → IMEA → Comex Stat → clima/ANA → Data Mart Soja MT → treino dos seis modelos iniciais → backtests point-in-time → relatório N6 integrado → auditoria de promoção. Em paralelo, `NEWS_SIGNAL` pode receber produtores reais apenas para fontes já homologadas, mantendo publicação externa bloqueada até os hard gates editoriais.