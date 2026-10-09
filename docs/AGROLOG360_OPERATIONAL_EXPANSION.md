# AgroLog MT 360 — Expansão operacional 51–100

Data-base: 2026-09-29.

## Objetivo

A expansão 51–100 transforma a fundação já construída em uma camada operacional de inteligência integrada sem criar uma segunda arquitetura.

Fluxo canônico:

```text
fonte → RAW/evidência → normalização → quality/freshness → BigQuery
→ marts_agrolog360 → AgroLog Gateway → cockpit/agentes → Obsidian
```

BigQuery permanece como fonte única de verdade analítica. Views/tabelas novas são criadas somente quando as dependências reais da fonte existem.

## Núcleo analítico adicionado

`models/agrolog_360.py`:
- precipitação acumulada 7/15/30/60/90 dias;
- balanço produção × capacidade estática;
- normalização de ofertas de frete para R$/t e R$/t.km;
- paridade de exportação;
- relação de troca fertilizante/grão;
- pressão portuária descritiva.

`models/agroclimate_events.py`:
- anomalia de precipitação contra climatologia;
- classificação percentílica transparente de seca/excesso hídrico.

`models/logistics_corridors.py`:
- corredor com tipo explícito EXPORT/DOMESTIC/IMPORT/TRANSFER/UNKNOWN;
- matriz origem-destino;
- agregação multimodal;
- custo multimodal.

`models/trade_codes.py`:
- leitura do contrato de NCM;
- bloqueio de dupla contagem;
- bloqueio de agregação automática quando o NCM exige vigência temporal.

## Contratos novos

- `agrolog_observation.v1.schema.json`;
- `agroclimate_daily.v1.schema.json`;
- `freight_offer_observation.v1.schema.json`;
- `biomass_observation.v1.schema.json`;
- `logistics_corridor.v1.schema.json`;
- `source_quality_freshness.v1.json`;
- `agrolog360_marts.v1.json`.

## Marts BigQuery

Dataset lógico: `marts_agrolog360`.

Planejados:
- `climate_rollups_v1`;
- `storage_balance_v1`;
- `freight_lanes_v1`;
- `fertilizer_imports_v1`;
- `biomass_v1`;
- `overview_current_v1`.

`scripts/apply_agrolog360_marts.py` verifica dependências reais primeiro. O dataset só é criado quando pelo menos um mart está pronto para ser aplicado com `--execute`.

## Fontes incorporadas ao control plane

Além das fontes já existentes, o Data Source Registry passa a conhecer explicitamente:
- ANTT RNTRC;
- MDF-e/movimentação pública legalmente acessível;
- EPE/SIEnergia biomassa;
- IBGE PEVS;
- SNIF;
- SEMA-MT/SISFLORA;
- ONS geração a biomassa;
- EPE BEN;
- ANP biometano;
- IBAMA DOF;
- Freight Listener autorizado.

Entrar no registry não significa produção. `planned` e `gated` continuam bloqueados para scheduler.

## Regras de biomassa

- volume agrícola × coeficiente de resíduo = `ESTIMADO`;
- geração elétrica observada = sinal de operação;
- guia florestal = movimentação observada;
- consumo industrial só pode ser `OBSERVADO` com declaração, licenciamento, relatório empresarial ou dado autorizado;
- DOF federal não substitui o sistema estadual de Mato Grosso para fluxos internos cobertos pelo sistema estadual.

## Freight Intelligence

A camada analítica usa apenas identificadores pseudonimizados do canal/mensagem.

`oferta observada ≠ contratado ≠ executado`.

Unidade ambígua ou confiança insuficiente mantém `requires_review=true`.

## Cockpit

O frontend existente foi ampliado para AgroLog MT 360:
- produção;
- capacidade estática;
- razão produção/capacidade;
- gap estático;
- chuva 7/30/90 dias;
- Maritime Intelligence continua na mesma tela.

Se os marts 360 ainda não existirem, a UI mostra `dados ainda gated` sem derrubar a camada marítima.

## Operação e CI

- diagnóstico de gate sem screenshots: `scripts/diagnose_final_gate.py`;
- guard de runner GCE órfão/custo: `scripts/audit_gce_ci_orphans.sh`;
- final release em GCE: `scripts/kick_final_release_gce.sh`;
- artifacts do GitHub foram reduzidos para evidência diagnóstica essencial.

## Critério para concluir o item 100

Não basta existir código. O mesmo SHA deve provar:
1. deterministic gate PASS;
2. LIVE/GCP gate PASS;
3. CONAB/Comex/Gateway homologados;
4. restore drill PASS;
5. zero LIVE skips;
6. `N6 CORE HOMOLOGATION: PASS`;
7. `AGROLOG MT FINAL RELEASE: PASS`;
8. promoção exata do SHA para `main`;
9. ruleset/readback da `main`.

Até isso ocorrer, a expansão é **implementada/preparada**, não declarada produção.
