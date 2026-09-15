# Governança de Dados

## Classificação obrigatória da evidência

Cada indicador, registro derivado ou conclusão deve ser classificado como uma das categorias abaixo:

1. **observado** — valor obtido diretamente de fonte oficial, contratada ou autorizada;
2. **inferido** — conclusão derivada de um ou mais dados/evidências;
3. **estimado** — valor calculado por coeficiente, aproximação ou método estimativo explícito;
4. **projetado** — valor referente ao futuro produzido por fonte/modelo/cenário;
5. **sinal_qualitativo** — informação não quantitativa material, preservando natureza e confiança;
6. **negociado_autorizado** — informação efetivamente negociada/operacional obtida de fonte interna ou autorizada.

Subtipos podem detalhar a natureza sem criar nova classe. Oferta de frete publicada em canal autorizado é `observado` com subtipo `oferta_frete_observada`; isso não prova contratação, execução ou preço pago.

## Classificação de segurança independente

A classe epistemológica não determina confidencialidade. Todo registro/artefato também obedece `PUBLIC`, `INTERNAL`, `CONFIDENTIAL` ou `RESTRICTED` conforme `docs/SECURITY.md`.

## Quatro datas e vintage

Preservar, quando aplicável:

- `data_referencia` — período/fato a que o dado se refere;
- `data_publicacao` — momento em que a fonte tornou o dado disponível;
- `data_coleta` — momento em que o AgroLog coletou/persistiu;
- `competencia` — período lógico (safra, mês, semana, marketing year etc.).

Fontes revisáveis, releases e forecasts também preservam:

- `vintage_id`/release/version;
- hash/referência do artefato quando disponível;
- collector/parser/normalization version;
- data de corte usada em estudo/backtest.

`data_referencia` nunca é tratada como data de disponibilidade. Backtests e análises históricas usam somente o vintage que já existia no corte.

## Camadas de confiança

Fluxo canônico:

`UNTRUSTED EXTERNAL → RAW/QUARANTINE → VALIDATED/SANITIZED → NORMALIZED → QUALITY GATE → CURATED`

### RAW / quarantine

- preservar artefato original quando permitido/necessário;
- registrar hash/provenance;
- nunca executar macro/script/instrução incorporada;
- conteúdo externo pode estar errado ou malicioso mesmo quando vem de domínio oficial.

### Normalized

- tipos/unidades/chaves/dimensões canônicas;
- transformação reproduzível;
- rejeições e warnings preservados;
- nenhuma correção silenciosa para tornar valor “plausível”.

### Curated

- somente após schema, row-count/tie-out, temporalidade, duplicidade e regras do domínio;
- lineage até fonte/RAW/transformação;
- freshness e quality status acessíveis ao consumidor;
- bloqueio quando condição crítica falha.

## Regras gerais

- Não apresentar estimativa/projeção/inferência como observado.
- Não afirmar frete real pago sem fonte autorizada.
- Não afirmar disponibilidade real de caminhões sem evidência operacional.
- Não atribuir volume a trading individual sem fonte que sustente a granularidade.
- Preservar fonte primária quando identificável, mesmo se uma agregadora facilitar aquisição.
- Manter snapshots/vintages quando a fonte pode revisar/remover dados retroativos.
- Toda transformação automatizada registra método/versão suficiente para reprocessamento.
- Extração por IA/visão preserva confiança e casos abaixo do limite são bloqueados/revistos.
- Programação portuária não é realizado; AIS não prova carga; ausência de fonte não é zero.
- Fallback é nova evidência identificada, nunca substituição silenciosa da fonte primária.

## Global Supply & Demand

O contrato canônico é `contracts/global_supply_demand.v1.schema.json`.

Balanços devem harmonizar, por commodity/país/marketing year/vintage:

- estoque inicial;
- produção;
- importação;
- oferta total;
- consumo doméstico;
- processamento;
- exportação;
- estoque final;
- stock/use.

Regras:

- unidade e marketing year são explícitos;
- release/vintage é imutável;
- revisão posterior cria novo vintage;
- divergência WASDE/PSD/AMIS/IGC/FAO/base nacional pode ser reconciliada analiticamente, mas a observação original permanece separada;
- totalizações derivadas são `inferido` quando não publicadas diretamente pela fonte.

## Forecasts

O contrato canônico é `contracts/forecast_vintage.v1.schema.json`.

Todo forecast preserva:

- emissão e horizonte;
- target/janela;
- point forecast e intervalo quando disponível;
- modelo/versão;
- training cutoff e feature cutoff;
- feature vintages;
- status `DRAFT/SHADOW/PROMOTED/SUPERSEDED/INVALIDATED`;
- resultado observado anexado posteriormente, sem reescrever o forecast original;
- métricas de erro/backtest.

Forecast sempre é `projetado`.

## News Impact e causalidade

O contrato `contracts/news_signal.v0_5.schema.json` pode registrar cadeia:

`EVENT → MECHANISM → COMMODITY → WORLD → BRAZIL → MATO_GROSSO`

A relação causal deve ser uma de:

- `CORRELATION`;
- `CAUSAL_HYPOTHESIS`;
- `SUPPORTED_CAUSALITY`.

Confiança/evidence IDs/explicações alternativas são preservados. Um modelo ou agente não pode promover correlação para causalidade apenas por plausibilidade textual.

## Ofertas de frete observadas

Regras obrigatórias:

- `classe_evidencia = observado`;
- `subtipo_evidencia = oferta_frete_observada`;
- `contratado = desconhecido` e `executado = desconhecido` por padrão;
- manter unidade anunciada; unidade incerta bloqueia conversão;
- agregados são valores da amostra de ofertas observadas;
- repostagens prováveis são deduplicadas/agregadas;
- reajuste/reoferta/persistência são eventos/sinais separados e versionados.

## Privacidade e minimização

- Preferir identificador pseudonimizado/hash quando nome não for necessário.
- Não expor telefone/nome/PII em dashboards analíticos por padrão.
- RAW autorizado permanece em armazenamento controlado, nunca no GitHub.
- Política de retenção/acesso/exclusão deve existir antes da ingestão real de canal privado.
- Credenciais/tokens/sessões/cookies nunca são versionados.
- Dados de canais só são ingeridos quando acesso/uso são autorizados.

## Linhagem mínima

Todo registro material deve apontar para:

- `source_id`/canal;
- evento/artefato/hash;
- `data_referencia`;
- `data_publicacao`;
- `data_coleta`;
- `competencia` quando aplicável;
- vintage/release;
- collector/parser/normalization version;
- transformações;
- confiança quando houver IA;
- dedup/reconciliation group quando aplicável.

## Qualidade mínima por carga

Registrar:

- registros lidos/aceitos/rejeitados;
- duplicidades;
- período coberto;
- timestamp;
- collector version;
- schema/quality result;
- row-count/tie-out;
- freshness;
- anomalias/warnings;
- resultado final.

Em stream/eventos, agregar por janela e incluir atraso, taxa de erro e volume descartado.

## Freshness e source health

O Data Source Registry versionado define expectativa/política; o estado vivo permanece no `collector_source_state`/logs operacionais.

Estados derivados mínimos:

- `HEALTHY`;
- `STALE`;
- `DEGRADED`;
- `FAILED`;
- `NEVER_COLLECTED`;
- ou estado estático `GATED/PLANNED/BLOCKED/DEPRECATED`.

GitHub não é atualizado a cada coleta. `collector/source_registry.py` sobrepõe `last_collection_at` a partir do estado operacional para gerar a visão corrente.

## Segurança e poisoning

Quality gate também é controle de segurança. Mudanças anormais de schema, volume, unidade, cardinalidade ou distribuição podem sinalizar quebra de fonte/data poisoning e bloquear curated. Controles adicionais estão em `docs/SECURITY.md`.