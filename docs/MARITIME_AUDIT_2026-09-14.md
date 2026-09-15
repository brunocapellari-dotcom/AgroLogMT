# AgroLog Maritime Intelligence — Auditoria de domínio
Data de corte: 2026-09-14

## Resultado executivo
O Maritime já possui base funcional relevante: ingestão AIS, persistência BigQuery, line-up oficial parcial dos cinco portos, reconciliação AIS x line-up, geofences governadas, Gateway/API e cockpit MapLibre/deck.gl. A atualização desta auditoria adiciona Source Registry, Quality Engine AIS, checkpoint lógico, heartbeat/reconnect e estado físico canônico.

A produção continua bloqueada por gates externos de infraestrutura/segurança e por dados ainda não homologados em todas as frentes. Nenhuma lacuna deve ser escondida com DEMO, geometria inventada ou inferência apresentada como observação.

## Auditoria por domínio

| Domínio | Estado | Evidência / decisão | Próximo gate |
|---|---|---|---|
| AIS | PARCIALMENTE PRONTO | AISStream client, raw JSON, normalização, retry/reconnect, Quality Engine, dedup em janela | credencial real + smoke GCP + histórico contínuo |
| Histórico | PARCIAL | BigQuery canônico; replay 24h disponível quando há dados | acumular histórico real e medir cobertura/gaps |
| Stream | ENDURECIDO | heartbeat, reconnect, retry, logical checkpoint, raw preservation | validar estabilidade live; AISStream não oferece offset/replay real |
| Portos | PARCIAL | cinco portos piloto canonizados | validar cobertura operacional real por porto |
| Line-up | PARCIAL | Santos/Vila do Conde/Santarém habilitados; Paranaguá/Itaqui ainda gated no registry específico | smoke oficial e freshness de todos os cinco |
| Vessel identity | EM IMPLEMENTAÇÃO | MMSI/IMO validation, conflito MMSI→IMO, match IMO/MMSI/nome | registry de identidade persistente + alias history |
| ETA | PARCIAL | ETA informado e erro de ETA presentes | ETA proprietário só após calibração/OOS |
| Port calls | PARCIAL | reconciliação + lifecycle oficial legado | migrar gradualmente para estado físico canônico sem perder semântica oficial |
| Geofences | GOVERNADO / GATED | contrato de proveniência, validação e bloqueio runtime | validar geometrias operacionais APPROACH/ANCHORAGE/BERTH |
| Filas | DATA_GATED | espera P50/P90 depende de geofence/eventos válidos | histórico confiável por porto |
| Berços | PARCIAL | terminal/berth quando fonte oficial permite | cobertura berth-level e QA por terminal |
| Mapa | PRONTO V1 | MapLibre + deck.gl + replay + vessel detail | tiles próprios/PMTiles quando necessário |
| Weather | DATA_GATED | Source Registry criado | definir fontes marítimas oficiais/especializadas e contratos de ingestão |
| Alertas | PARCIAL | divergências/reconciliation/source health existem | rules engine formal + severidade + cooldown/dedup de alertas |
| APIs | PRONTO EM CÓDIGO / INFRA GATED | Gateway Maritime e hardening de segurança | deploy privado real, IAM e smoke |
| Storage | PRONTO EM CÓDIGO | BigQuery shipping_* + RAW/canonical; stream checkpoints adicionados | validar carga real, custo e retenção |

## Segurança AIS aplicada
- MMSI deve ser válido e não vazio;
- IMO, quando presente, passa por formato e checksum;
- timestamps inválidos/futuros/não monotônicos são sinalizados;
- posição inválida é bloqueada;
- implied speed excessivo gera `impossible_speed`;
- salto espacial incompatível gera `teleport`;
- mudança de IMO no mesmo MMSI gera `identity_conflict_mmsi_to_imo`;
- combinação de múltiplas anomalias pode gerar `spoofing_suspected`;
- uma única mensagem AIS nunca confirma estado físico;
- registros suspeitos permanecem preservados para auditoria, mas não alimentam geofence operacional.

## Stream semantics
AISStream é tratado como stream sem replay histórico garantido. O AgroLog registra checkpoint lógico próprio com último `observation_id`, timestamp e contadores persistidos. `upstream_offset` permanece `null` e `replay_capable=false`; nunca apresentar esse checkpoint como offset recuperável do fornecedor.

## Storage target
BigQuery permanece a fonte analítica histórica canônica. PostGIS + TimescaleDB ficam como camada hot/operacional futura para consultas espaciais/temporais de baixa latência quando benchmarks justificarem custo e complexidade. Não criar segunda fonte de verdade.

## Gates obrigatórios antes de produção
1. `unit-tests` e `security-gate` verdes;
2. `main` protegida com ruleset/branch protection;
3. WIF/GCP validado sem chaves de service account;
4. AISStream secret apenas em Secret Manager;
5. Gateway sem `allUsers`;
6. captura AIS real em cinco AOIs com heartbeat e checkpoints persistidos;
7. line-up oficial real nos cinco portos ou status `DATA_GATED` explícito onde faltar;
8. geofences operacionais somente com `GEOFENCE_VALIDATED=1`;
9. smoke end-to-end documentado;
10. Maritime Auditor aprovando freshness, evidência e direitos de uso.
