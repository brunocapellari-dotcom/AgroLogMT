# CFTC Commitments of Traders — avaliação (Issue #14, subconjunto sem chave)

Avaliação do relatório semanal **Commitments of Traders (COT)** da
[CFTC Public Reporting](https://publicreporting.cftc.gov/), conforme pedido
pela Issue #14: "registrar metadados, autenticação, limites e calendários
de publicação" antes de qualquer carga no BigQuery. **Nenhum dado foi
carregado no BigQuery nesta avaliação.**

A Issue #14 lista quatro fontes aprovadas: USDA FAS Open Data, USDA NASS
Quick Stats, USDA AMS MyMarketNews e CFTC Commitments of Traders. Esta
avaliação cobre **apenas o CFTC COT**, porque foi a única, testada
diretamente nesta sessão, que respondeu com dados reais sem exigir
registro de API key — consistente com a regra da Fase D de priorizar
fontes "que não exijam compra/chave nova". As outras três seguem
registradas como blocker de credencial (ver seção "Fontes da Issue #14
fora do escopo desta avaliação").

## Plataforma e acesso

- Domínio: `publicreporting.cftc.gov`, operado pela
  Commodity Futures Trading Commission (CFTC) dos EUA.
- Motor: [Socrata Open Data (SODA)](https://dev.socrata.com/), mesmo padrão
  já validado no projeto para `agtransport.usda.gov` (Issue #20) — API REST
  JSON, sem necessidade de autenticação para leitura pública.
- Metadados de um dataset: `GET /api/views/{dataset_id}.json`.
- Registros: `GET /resource/{dataset_id}.json` com parâmetros SoQL
  (`$select`, `$where`, `$order`, `$limit` até 50000, `$offset`).
- Conectividade real confirmada nesta avaliação: chamadas diretas aos
  endpoints acima (Python `urllib.request`) e depois via testes
  automatizados em `cftc_cot/tests/test_datasets_live.py`.
- Licença/atribuição declaradas pela API: ambas `None` no dataset avaliado.
  Trata-se de dado público oficial do governo dos EUA (obra do governo
  federal, domínio público), atribuição de fato usada em publicações do
  próprio CFTC: **"CFTC"**.

## Dataset avaliado

Existem três variantes do relatório COT no catálogo CFTC (confirmado via
`GET /api/views/{id}.json` para cada candidato):

| Relatório | ID | Observação |
|---|---|---|
| Legacy — Combined | `jun7-fc8e` | Agregação mais antiga/simples, sem separar produtor/comercial de fundo especulativo. |
| Disaggregated — Futures Only | `72hh-3qpy` | Igual ao escolhido, mas sem posições de opções. |
| **Disaggregated — Combined** | **`kh3c-gbw2`** | **Escolhido.** Futuros + opções combinados, com posição líquida separada em Producer/Merchant, Swap Dealers, Managed Money e Other Reportables — granularidade padrão usada em análise de sinal especulativo/comercial de commodities agrícolas. |

Category declarada pela API: `Commitments of Traders`. `rowsUpdatedAt` do
dataset em `2026-08-14T19:30:10Z` no momento desta avaliação — consistente
com publicação semanal (toda sexta-feira, dados de posição de terça-feira).

### Contratos filtrados (dentro do dataset único)

O dataset cobre todos os mercados sob jurisdição do CFTC num único
recurso; a seleção de commodity é feita por `$where` sobre
`market_and_exchange_names`. Dois contratos foram validados nesta
avaliação, seguindo a prioridade soja→milho já usada no restante do
projeto:

| Chave | `market_and_exchange_names` | Código | Relevância MT |
|---|---|---|---|
| `soybeans_cbot` | `SOYBEANS - CHICAGO BOARD OF TRADE` | `005602` | direta |
| `corn_cbot` | `CORN - CHICAGO BOARD OF TRADE` | `002602` | direta |

Atenção: o mesmo dataset também tem um contrato `MINI SOYBEANS - CHICAGO
BOARD OF TRADE` com open interest ~45x menor (26.470 contra 1.203.233 em
11/08/2026) — descartado por não ser a referência de mercado. O teste
`test_soybeans_cbot_open_interest_is_far_larger_than_mini_soybeans` existe
para prevenir uma regressão de filtro que passe a casar o contrato errado.

### Amostra real — soja padrão CBOT (`kh3c-gbw2`, 2026-08-11)

```json
{
  "report_date_as_yyyy_mm_dd": "2026-08-11T00:00:00.000",
  "market_and_exchange_names": "SOYBEANS - CHICAGO BOARD OF TRADE",
  "cftc_contract_market_code": "005602",
  "open_interest_all": "1203233",
  "prod_merc_positions_long": "378451",
  "prod_merc_positions_short": "589059",
  "swap_positions_long_all": "150805",
  "swap__positions_short_all": "42246",
  "m_money_positions_long_all": "164515",
  "m_money_positions_short_all": "63153",
  "other_rept_positions_long": "59239",
  "other_rept_positions_short": "33820"
}
```

Cadência real confirmada por três registros consecutivos de
`SOYBEANS - CHICAGO BOARD OF TRADE`: `2026-08-11`, `2026-08-04`,
`2026-07-28` — intervalos de 7 dias, semanal como esperado.

## Classificação de evidência

Seguindo `docs/DATA_GOVERNANCE.md` (dado observado vs. inferência vs.
estimativa vs. informação negociada):

- **Observado/oficial**: todo o dataset — o COT é uma série publicada
  diretamente pela CFTC a partir de dados de posição reportados por
  corretoras/clearing houses sob obrigação regulatória, não uma estimativa
  ou modelo do próprio AgroLog.
- As colunas de posição (`prod_merc_*`, `swap_*`, `m_money_*`,
  `other_rept_*`) são a decomposição publicada pela própria CFTC, não um
  cálculo derivado do AgroLog — nenhuma transformação é aplicada nesta
  avaliação além de seleção de colunas/filtro.

## Qualidade e limitações observadas

- Sem chave/token obrigatório para os volumes consultados nesta avaliação;
  `SocrataClient` aceita `app_token` opcional para cenários de maior
  volume, igual ao cliente AgTransport.
- Datas em `report_date_as_yyyy_mm_dd` (string ISO sem timezone) —
  precisam de normalização explícita antes de qualquer comparação com
  séries brasileiras (CONAB, IMEA) que já usam `data_referencia` em
  UTC-3 implícito. Mesma limitação já documentada para AgTransport.
- O dataset é **global por contrato**, sem recorte geográfico
  brasileiro/MT — a relevância para o MT é indireta: sinaliza
  posicionamento especulativo/comercial no mercado futuro de referência
  (CBOT) que precifica a soja/milho exportados pelo MT, não uma métrica
  originada no Brasil. Qualquer uso futuro deve documentar isso
  explicitamente como contexto de mercado internacional, não como dado
  brasileiro.
- Nenhuma indicação de descontinuação; `rowsUpdatedAt` mostra atualização
  recente (dentro da mesma semana da avaliação).

## Fontes da Issue #14 fora do escopo desta avaliação

Testadas diretamente nesta sessão (chamada HTTP real, sem key, para
confirmar o tipo de bloqueio antes de registrar como blocker):

| Fonte | Endpoint testado | Resultado | Bloqueio |
|---|---|---|---|
| USDA AMS MyMarketNews | `GET https://marsapi.ams.usda.gov/services/v1.2/reports` | `HTTP 403 Forbidden` — `"Attempt to access the protected resource"` | Exige registro de API key. |
| USDA FAS Open Data (PSD) | `GET https://apps.fas.usda.gov/OpenData/api/psd/commodities` | Timeout de conexão (rede) | Exige `X-Api-Key` por documentação oficial; não foi possível nem confirmar o tipo de erro por bloqueio de rede neste ambiente. |
| USDA NASS Quick Stats | `GET https://quickstats.nass.usda.gov/api/api_GET/?key=DEMO_KEY` | `HTTP 401 Unauthorized` — `{"error":["unauthorized"]}` | Exige registro de API key real (chave demo não é aceita). |

Todas as três exigem "chave nova" no sentido da regra de Fase D
("fontes... que não exijam compra/chave nova") e ficam fora do escopo
desta rodada. A ser registrado como blocker de credencial (não falha
técnica do AgroLog) em `docs/NIGHT_RUN_BLOCKERS.md`, mantido na branch
`chore/night-run-reports-48h` (PR #28), não nesta branch de feature.

## Termos de uso

Dado público do governo federal dos EUA (CFTC), sem chave de API
obrigatória para os endpoints de leitura usados. Licença/atribuição
declaradas pela API como `None` — domínio público padrão de obras do
governo federal dos EUA. Atribuição a manter em qualquer uso derivado:
**CFTC**.

## Código

`socrata_connector/` — cliente Python genérico somente leitura para APIs
SODA (`SocrataClient`), extraído nesta avaliação porque
`usda_agtransport.client` (Issue #20) já implementava a mesma lógica de
forma duplicada. `cftc_cot/` — `build_client()` (cliente travado no host
CFTC) e registro dos contratos avaliados (`KNOWN_CONTRACTS`). Ver
`cftc_cot/README.md` e `socrata_connector/README.md` para uso, testes e o
aviso de segurança sobre cláusulas SoQL.

## Próximos passos (não executados nesta avaliação)

1. Decidir schema de destino (dataset/tabela) no BigQuery seguindo o mesmo
   padrão de `data_referencia`/`data_publicacao`/`data_coleta`/
   `competencia` usado pelas demais fontes do projeto — aqui
   `data_referencia` seria `report_date_as_yyyy_mm_dd` (terça-feira da
   posição) e `data_publicacao` a sexta-feira seguinte (não vem no payload;
   precisaria ser calculada ou obtida do calendário oficial de publicação
   do CFTC).
2. Quando a PR #29 (AgTransport) mesclar, migrar `usda_agtransport` para
   consumir `socrata_connector` em vez do `SocrataClient` duplicado que
   ainda existe naquela branch — não feito nesta avaliação por não editar
   uma branch de PR de outra sessão sem coordenação.
3. Reavaliar USDA FAS Open Data, NASS Quick Stats e AMS MyMarketNews
   quando houver decisão humana sobre registro de API key — não faz parte
   do escopo "sem bloqueio humano" da Fase D.
4. Só considerar carga real no BigQuery depois de (1) e da revisão de DQ,
   seguindo o mesmo processo de piloto validado usado para CONAB Armazéns.
