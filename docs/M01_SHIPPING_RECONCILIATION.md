# M01-S — Shipping & Port Reconciliation

## Objetivo

Cruzar **line-up portuário × AIS × eventos operacionais/realizados** para que o AgroLog diferencie claramente programação de execução.

## Regra editorial e operacional

Estados externos principais:

1. `PROGRAMMED` — consta no line-up, sem confirmação operacional;
2. `IN_TRANSIT` / `APPROACHING` — AIS confirma deslocamento/aproximação;
3. `ARRIVED_WAITING` — AIS/operação confirma chegada/fundeio;
4. `BERTHED` — AIS ou fonte portuária confirma atracação;
5. `DEPARTED_PENDING_REALIZED` — AIS confirma saída, mas a operação realizada ainda não foi confirmada;
6. `COMPLETED_REALIZED` — somente fonte operacional/portuária observada confirma conclusão.

**AIS de saída nunca transforma sozinho um line-up em REALIZADO.**

## Identidade do navio

Prioridade de matching:

1. IMO exato — confiança 1,00;
2. MMSI exato — confiança 0,99;
3. nome normalizado/fuzzy — fallback, sujeito a porto, terminal e janela temporal.

Conflito de IMO ou MMSI bloqueia match fuzzy. Isso evita ligar dois navios diferentes apenas porque o nome é parecido.

## Fontes

### Line-up
Programação declarada por porto/terminal/operador.

Campos mínimos:
- call_id;
- snapshot_id;
- porto;
- terminal;
- nome;
- IMO/MMSI quando disponível;
- ETA;
- produto;
- volume programado;
- status do line-up;
- collected_at.

### AIS
O adapter inicial normaliza mensagens compatíveis com AISStream.
AIS deve preservar dados brutos/observados e não inferir terminal ou porto antes da camada de geofence.

Campos:
- MMSI;
- IMO quando disponível;
- nome;
- timestamp;
- lat/lon;
- SOG/COG;
- navigation status;
- destination.

### Operação portuária
Fonte observada usada para confirmar realizado:
- chegada;
- atracação;
- desatracação;
- conclusão;
- volume efetivo;
- status operacional.

Pode vir de SPA/portos/ANTAQ/terminal ou outra fonte autorizada, preservando metodologia.

## Geofences

O modelo aceita zonas normalizadas:
- `SEA`;
- `APPROACH`;
- `ANCHORAGE`;
- `BERTH`;
- `DEPARTED`;
- `UNKNOWN`.

A criação e versão dos polígonos de fundeadouro/berço é uma camada separada. Não deve ser embutida no parser AIS bruto.

## Métricas

Por escala/navio:
- erro ETA em horas;
- espera chegada→berço;
- tempo de berço;
- variação volume programado×realizado;
- flags de divergência.

Por porto/terminal:
- `Line-up Reliability Score`;
- share realizado;
- share AIS matched;
- distribuição de erro ETA;
- espera P50/P90/P95;
- atraso/cancelamento/divergência.

O Reliability Score v0.1 é **descritivo**, não modelo preditivo.

## BigQuery

Tabelas em `agrolog_models`:
- `shipping_lineup_calls`;
- `shipping_ais_positions`;
- `shipping_port_operations`;
- `shipping_reconciliation`.

A implementação está em `collector/shipping_bigquery.py`.

## Integração com M01

O M01-S produz features/targets para o Índice de Pressão Logística:
- waiting_hours;
- berth_hours;
- eta_error_hours;
- navios aguardando;
- divergência line-up×AIS;
- atraso da programação;
- capacidade efetivamente realizada;
- reliability por terminal/porto.

Isso entra no M01 junto com frete, MDF-e, ferrovia, hidrovias e fluxo portuário.

## Piloto

Ordem:
1. Santos;
2. Paranaguá;
3. Barcarena/Vila do Conde;
4. Santarém;
5. Miritituba/Itaituba.

A expansão depende da qualidade e cobertura de AIS + line-up + fonte observada de operação.

## Gate

Estado inicial: `DATA_PILOT`.

Para `BACKTEST`:
- line-up versionado historicamente;
- AIS histórico próprio ou autorizado;
- eventos observados de operação;
- entity resolution auditada;
- geofences versionadas;
- métricas sem look-ahead.

Para `OPERATIONAL`:
- captura recorrente;
- QA de cobertura;
- alertas de divergência;
- histórico suficiente para thresholds de espera/atraso.
