# AgroLog MT — Onda Operacional de 30 passos — 25/08/2026

Objetivo: fechar o máximo possível do caminho crítico sem criar nova automação/tarefa e sem declarar produção onde falta evidência autenticada.

## Legenda
- `DONE`: concluído e reproduzível no nível indicado.
- `DONE_CODE`: código/contrato/teste concluído; runtime produtivo ainda gated.
- `READY_GCP`: pronto para execução no ambiente autenticado GCP.
- `BLOCKED_GCP`: não pode ser fechado sem execução real autenticada.
- `PARTIAL_SOURCE`: fonte/contrato existe, mas cobertura/freshness ainda incompleta.
- `GATED`: deliberadamente não materializar/promover antes dos pré-requisitos.

## Status dos 30 passos

| # | Passo | Estado | Evidência / próximo gate |
|---:|---|---|---|
| 1 | Consolidar estado canônico de manhã | DONE | MOC/rotinas corrigidos para taxonomia não sobreposta, PTAX temporal e Portos multiporto |
| 2 | Recalcular Launch Readiness sem inflação editorial | DONE | estado operacional mantém manual gate; Portos rebaixado para `PARTIAL_MULTI_PORT`; não declarar 95% |
| 3 | Consolidar P0/P1 em comando único | DONE | `scripts/homologate_n6_core.sh` |
| 4 | Verificar IAM mínimo | DONE_CODE | BigQuery `user` no projeto + `dataEditor` apenas em datasets canônicos; sem `bigquery.admin` |
| 5 | Executar preflight GCP real | BLOCKED_GCP | requer `gcloud`/`bq` autenticados; `scripts/preflight_n6_gcp.sh` pronto |
| 6 | Redeployar collector da `main` | READY_GCP | deploy preparado; Scheduler agora `MANAGE_SCHEDULER=0` por padrão |
| 7 | Executar CONAB Armazéns atual | BLOCKED_GCP | `AGROLOG_SOURCE_ID=conab_armazens_cadastrados` |
| 8 | Auditar RAW + manifesto | BLOCKED_GCP | `validate_conab_n6.py` exige hash, Drive RAW/readback e manifesto real |
| 9 | Auditar conteúdo BigQuery | BLOCKED_GCP | comparar schema/runtime atual contra benchmark histórico, sem tratá-lo como P0 atual |
| 10 | Segunda execução/idempotência | BLOCKED_GCP | deve resultar sem duplicação/novo snapshot material |
| 11 | Homologar Gateway atual | BLOCKED_GCP | `scripts/deploy_gateway_gcloud.sh` |
| 12 | Comparar Gateway × BigQuery | BLOCKED_GCP | `scripts/validate_gateway_n6.py` |
| 13 | Comparar OpenAI/Codex × Claude | BLOCKED_GCP | somente após endpoint real e leitura controlada |
| 14 | Fechar P0/P1 | BLOCKED_GCP | só após PASS dos validadores e comparação multiagente |
| 15 | Ativar CONAB Safra pós-P0/P1 | DONE_CODE / GATED | parser, loader, PIT e live probe prontos; fonte continua `enabled=false` |
| 16 | Carregar vintages históricos CONAB | DONE_CODE / GATED | registry profundo 2010+; timestamps não verificáveis permanecem bloqueados |
| 17 | Ativar pipeline IMEA autorizado | DONE_CODE / GATED | Drive→RAW→QA→BigQuery pronto; `enabled=false` até P0/P1 e share SA |
| 18 | Validar IMEA por domínio | DONE_CODE | parser/QA separa indicadores, progresso e frete; frete continua referência, não negociado |
| 19 | Supersession IMEA por competência | PARTIAL_SOURCE | contratos temporais existem; execução real depende de workbook atualizado e carga canônica |
| 20 | Integrar Produção × Comercialização sem duplicidade | DONE_CODE | `contracts/editorial_taxonomy.v1.json` congela `SAFRA_PRODUCAO` × `MERCADO_COMERCIALIZACAO` |
| 21 | Fechar ANA live 5 estações | BLOCKED_GCP | cliente HidroWebService pronto; secrets devem entrar por runtime seguro/Secret Manager |
| 22 | Deltas hidrológicos 1/3/7/15 dias | DONE_CODE | `models/hydrology.py`; endpoints reais obrigatórios, sem interpolação |
| 23 | Climatologia hidrológica por dia do ano | DONE_CODE | P01/P05/P10/P25/P50/P75/P90/P95/P99; exige histórico real suficiente |
| 24 | Cruzar hidrologia com navegação real | DONE_CODE | `NavigationEvent`; restrição nunca inferida apenas pelo nível |
| 25 | Cobertura multiporto | PARTIAL_SOURCE | contrato exige Santos + Paranaguá/Antonina + Arco Norte; fontes oficiais identificadas, freshness completa pendente |
| 26 | Lifecycle DUV/IMO | DONE_CODE / PARTIAL_SOURCE | `PortCallState` + transições explícitas; dados correntes multiporto ainda precisam ingestão oficial |
| 27 | Resolver Comex Stat/MDIC | PARTIAL_SOURCE | parser/loader e diagnóstico TLS prontos; runner ainda precisa caminho TLS oficial estável |
| 28 | Materializar Data Mart Soja MT V0.1 | GATED | produção/storage/clima têm base local; market/trade/cloud QA ainda impedem materialização integrada |
| 29 | Executar backtests reais Soja MT | PARTIAL / GATED | PAM/IBGE 1974–2024 + hurdles CONAB já executados; suite integrada aguarda Data Mart PIT-ready |
| 30 | Primeira edição operacional AgroLog Beta | PARTIAL | News/relatórios em gate manual já são utilizáveis; edição integrada definitiva depende de P0 e freshness das frentes acima |

## Mudanças desta onda
1. `collector/bcb_ptax.py`: PTAX USD por endpoint oficial BCB/Olinda; somente boletim explícito `Fechamento` vira closing do dia.
2. `collector/port_lifecycle.py`: contrato multiporto e lifecycle `PROGRAMADO → ATRACADO → DESATRACADO → CONCLUIDO`; volume programado nunca é realizado.
3. `models/hydrology.py`: deltas observados 1/3/7/15, climatologia por percentis e vínculo com eventos de navegação sem inferência indevida.
4. `contracts/editorial_taxonomy.v1.json`: famílias editoriais não sobrepostas e gates canônicos.
5. `scripts/deploy_collectors_gcloud.sh`: Cloud Scheduler passa a ser opt-in (`MANAGE_SCHEDULER=0` por padrão), evitando criação de recorrências durante homologação P0/P1.

## Único caminho crítico externo
Após merge desta onda, em ambiente autenticado:

```bash
PROJECT_ID=<projeto> MANAGE_SCHEDULER=0 bash scripts/homologate_n6_core.sh
```

A execução deve produzir evidência de preflight, deploy, duas cargas CONAB, idempotência, Gateway e equivalência Gateway×BigQuery. Não promover P0/P1 sem esses artefatos.

## Regras de segurança
- Nenhum segredo no Git/Drive/Obsidian/log.
- ANA/USDA/IMEA autenticados somente por Secret Manager/variáveis seguras.
- Não desabilitar TLS para Comex.
- Não criar Cloud Scheduler no P0/P1 por padrão.
- Não publicar externamente sem gate humano.
