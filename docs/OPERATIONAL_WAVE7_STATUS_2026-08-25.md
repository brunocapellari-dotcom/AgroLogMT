# AgroLog MT — Onda 7/8 — execução dos 30 itens

Data de corte: 2026-08-25.

Regra: `concluído` exige evidência; código pronto sem execução cloud é `pronto para executar`, não carga concluída.

| # | Item | Estado | Resultado |
|---:|---|---|---|
| 1 | BigQuery M01/M02/M07 + tie-out | PRONTO PARA EXECUTAR | Store canônico + lineage implementados; execução cloud depende do preflight GCP. |
| 2 | `data_lineage` | IMPLEMENTADO | tabela e writer no `OperationalModelsBigQueryStore`. |
| 3 | ANP incremental | IMPLEMENTADO | coletor CSV, latest competence e agregação MT. |
| 4 | matéria-prima jul/26 | PENDENTE FONTE | produção de etanol jul/26 disponível; matéria-prima mensal deve ser incorporada quando publicada. |
| 5 | M02 v0.2 2018–26 | PARCIAL | metodologia ramp-adjusted criada; recalibração integral depende da carga canônica. |
| 6 | regionalização M02 | DADOS_PILOTO | plant master e capacidade existem; regionalização final depende de produção/armazenagem/rodovias sincronizadas. |
| 7 | absorption_30d | IMPLEMENTADO PILOTO | função low/base/high implementada. |
| 8 | ferrovia mensal | DADOS MATERIALIZADOS | base ANTT/SIADE processada; fluxos MT relevantes documentados. |
| 9 | share modal rodovia×ferrovia | PARCIAL | só calcular onde universos/denominadores forem compatíveis. |
| 10 | port_flow_master | PARCIAL | Santos estruturado; Paranaguá/Arco Norte em integração. |
| 11 | 78 mensários Santos | 76/78 EXTRAÍDOS | jan/fev 2023 continuam exceções de parsing. |
| 12 | fila diária Santos | INICIADO | snapshot operacional existe; série diária começa por captura incremental. |
| 13 | fila demais portos | INICIADO | fontes catalogadas; sem histórico diário suficiente ainda. |
| 14 | M01 treino 2023–25/teste 2026 | PARCIAL | backtest frete×MDF-e executado; pipeline temporal em evolução. |
| 15 | baseline M01 | IMPLEMENTADO BASE | funções de percentil/z-score/pressure label e regime shifts adicionadas. |
| 16 | HidroWeb 2024–26 | BLOQUEIO RUNTIME | credencial existe de forma segura; runtime ChatGPT não injeta headers. Workflow cloud agora testa disponibilidade. |
| 17 | target operacional M04 | PARCIAL | schema/labels definidos; falta histórico consistente de calado/lote/avisos/interrupções. |
| 18 | backtest M04 | BLOQUEADO CORRETAMENTE | não executar falso backtest apenas contra nível do rio. |
| 19 | M04 v1 shadow | NÃO PROMOVIDO | só após superar baseline. |
| 20 | weather M07 | PRONTO PARA PIPELINE | repo já possui NASA POWER/climate-grid/Copernicus; execução cloud pendente. |
| 21 | ETo/VPD/água solo | PARCIAL | ETo e modelo agroclimático já existem; água no solo precisa de dados materializados/QA. |
| 22 | weather×fenologia | PRONTO | fenologia IMEA point-in-time 2020–26 já extraída; weather falta. |
| 23 | backtest M07 5 safras | BLOQUEADO POR WEATHER | não promover sem série meteorológica point-in-time. |
| 24 | baseline M07 | INFRA EXISTENTE | `models/baselines.py`, backtest/evaluation/promotion já existem. |
| 25 | M05 comparável | NÃO PROMOVIDO | terminal/regime comercial/timing ainda incompletos. |
| 26 | M03 multi-safra | DADOS_PILOTO | série 2025/26 + mecanismo armazenagem validados; multi-safra ainda precisa normalização. |
| 27 | M06 mensal | DADOS_PILOTO | caso 2021–22 validado; série mensal quantitativa ainda incompleta. |
| 28 | M08 empresas | DADOS_PILOTO | Rumo, SLC e São Martinho iniciados; expansão para Raízen e demais continua. |
| 29 | Shadow #002 | BLOQUEADO CORRETAMENTE | não registrar até M04/M07/M01 corrigidos; #001 permanece imutável. |
| 30 | LAB-004 | PARCIAL | encadeamento metodológico existe; previsão final fica bloqueada pelos mesmos gates de M04/M07/M05. |

## Entregas de engenharia desta onda

- `models/operational_models.py`: M01/M02/M04 + gates.
- `collector/operational_models_bigquery.py`: tabelas canônicas de observações, scores e lineage.
- `collector/anp_bioenergy.py`: ingestão pública incremental ANP.
- testes unitários para os novos componentes.
- workflow `operational-models-readiness.yml`: CI + ANP live probe + preflight GCP + ANA live probe condicional.

## O que não foi falsamente declarado

- nenhuma carga BigQuery foi declarada executada antes do preflight cloud;
- nenhuma restrição de navegação foi inferida somente por nível de rio;
- nenhum M07 quantitativo foi validado sem weather point-in-time;
- M05 não foi chamado de comparável sem todos os custos;
- Shadow #002 não foi criado para inflar maturidade.
