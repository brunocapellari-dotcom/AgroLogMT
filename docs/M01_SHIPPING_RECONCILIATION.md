# M01-S — Shipping & Port Reconciliation

## Objetivo

Cruzar **line-up portuário × AIS × eventos operacionais/realizados** para que o AgroLog diferencie claramente programação de execução.

## Regra editorial e operacional

Estados externos principais:

1. `PROGRAMMED` — consta no line-up, sem confirmação operacional;
2. `IN_TRANSIT` / `APPROACHING` — AIS confirma deslocamento/aproximação;
3. `ARRIVED_WAITING` — AIS/operação confirma chegada/fundeio;
4. `BERTHED` — AIS ou fonte portuária confirma presença em geofence de berço validada ou atracação observada;
5. `DEPARTED_PENDING_REALIZED` — AIS confirma/informa uma saída compatível, mas a operação realizada ainda não foi confirmada;
6. `COMPLETED_REALIZED` — somente fonte operacional/portuária observada confirma conclusão.

**AIS de saída nunca transforma sozinho um line-up em REALIZADO.**

Quando não existe uma zona explícita `DEPARTED`, o port-call engine pode reconhecer a sequência `BERTH → SEA/APPROACH` como evidência de saída. Esse timestamp é tratado como **limite superior observado da saída**, recebe a flag `ais_departure_from_berth_exit_transition` e permanece `DEPARTED_PENDING_REALIZED`. Uma fonte operacional de desatracação substitui esse limite quando disponível.

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
O adapter normaliza mensagens AISStream. AIS deve preservar dados brutos/observados e não inferir terminal ou porto antes da camada de geofence.

Campos:
- MMSI;
- IMO quando disponível;
- nome;
- timestamp;
- lat/lon;
- SOG/COG;
- navigation status;
- destination.

Como o serviço de streaming não oferece replay durável, o AgroLog persiste o JSON bruto recebido junto da observação normalizada no BigQuery. Isso permite auditoria e reprocessamento próprio.

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
- `UNKNOWN`.

`DEPARTED` continua aceito como estado AIS explícito quando uma fonte/processo confiável o fornecer, mas não é necessário para detectar saída na V1.

A criação e versão dos polígonos de aproximação, fundeadouro e berço é uma camada separada. Não deve ser embutida no parser AIS bruto e **não pode usar polígonos inventados**. Cada classificação deve ser reproduzível pela versão da geofence utilizada.

O contrato `contracts/maritime_geofences.v1.json` exige fonte, versão, validação e geometria plausível. `models/port_geofence.py` bloqueia coordenadas fora dos limites físicos e polígonos degenerados antes de classificar uma posição.

## Captura AIS ao vivo

Implementação:
- `collector/ais_stream_client.py` — WebSocket, compressão, assinatura, timeout e reconnect/backoff;
- `collector/ais_worker.py` — geofence + batching + BigQuery + preservação do raw JSON;
- `scripts/setup_aisstream_secret.sh` — cadastro one-shot da chave AISStream no Secret Manager e, quando disponível, GitHub Actions;
- `scripts/deploy_ais_worker_gcloud.sh` — deploy do Cloud Run Job e agendamento;
- `.github/workflows/ais-live-probe.yml` — teste manual de conectividade sem revelar a chave.

A bounding box de assinatura AIS é apenas filtro de aquisição; **não é geofence operacional**.

## Reconciliação automática

`collector/shipping_reconcile_worker.py` lê do BigQuery:
- último snapshot de cada escala do line-up;
- observações AIS da janela;
- último evento portuário por escala;

e executa o batch `line-up × AIS × operação`, gravando `shipping_reconciliation`.

O resultado inclui:
- estado atual;
- método/confiança do match;
- ETA error;
- waiting time;
- berth time;
- volume variance;
- divergências e alertas;
- método de detecção da saída quando aplicável.

## API e tela Maritime V1

O AgroLog Gateway expõe leituras específicas para a interface operacional:

- `/v1/maritime/config`;
- `/v1/maritime/vessels` — posição AIS mais recente por navio;
- `/v1/maritime/vessels/{mmsi}/replay` — trajetória histórica para replay;
- `/v1/maritime/lineup` — último line-up cruzado com última reconciliação;
- `/v1/maritime/summary` — contagens e estatísticas derivadas existentes.

A interface `maritime_ui` usa **MapLibre + deck.gl**, é compilada dentro da mesma imagem do Gateway e servida em `/maritime/`. Em produção usa a API same-origin, preservando o Gateway privado. O enquadramento do mapa usa posições AIS retornadas; não existem coordenadas portuárias aproximadas hardcoded na tela.

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

A tela V1 publica somente métricas sustentadas pelas tabelas atuais. **DWT em espera, carga efetiva e volume realizado não são inferidos** quando a evidência necessária não existe.

O Reliability Score v0.1 é **descritivo**, não modelo preditivo.

## BigQuery

Tabelas em `agrolog_models`:
- `shipping_lineup_calls`;
- `shipping_ais_positions`;
- `shipping_port_operations`;
- `shipping_reconciliation`.

A implementação está em `collector/shipping_bigquery.py`. Escritas usam IDs estáveis para reduzir duplicação em retries; a auditoria continua dependendo da preservação de snapshot/source timestamps.

## Integração com M01

O M01-S produz features/targets para o Índice de Pressão Logística:
- waiting_hours;
- berth_hours;
- eta_error_hours;
- navios aguardando;
- divergência line-up×AIS;
- atraso da programação;
- capacidade efetivamente realizada quando observada;
- reliability por terminal/porto.

Isso entra no M01 junto com frete, MDF-e, ferrovia, hidrovias e fluxo portuário.

## Piloto Maritime V1

Ordem e IDs canônicos:
1. `SANTOS` — Santos;
2. `PARANAGUA` — Paranaguá;
3. `BARCARENA_VILA_DO_CONDE` — Barcarena/Vila do Conde;
4. `SANTAREM` — Santarém;
5. `ITAQUI` — Itaqui.

Os IDs legados `PARANAGUA_ANTONINA` e `ARCO_NORTE_CDP` permanecem legíveis para auditoria histórica, mas não satisfazem o gate de cobertura individual da V1.

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

## Ativação

O código pode ser implantado sem alterar a regra de governança. Para **ativar AIS ao vivo**, é necessária uma API key AISStream armazenada server-side. A chave nunca deve ser enviada no chat ou hardcoded no repositório.

O deploy do Gateway concede leitura somente às tabelas canônicas existentes e mantém `--no-allow-unauthenticated`. Para acesso interativo, pode-se usar `gcloud run services proxy` e abrir `/maritime/` localmente.
