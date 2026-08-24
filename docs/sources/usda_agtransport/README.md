# USDA AgTransport — avaliação (Issue #20)

Avaliação da plataforma [Open Ag Transport Data](https://agtransport.usda.gov/)
do USDA AMS (que hospeda os dados por trás do Grain Transportation Report —
GTR — e do Grain Truck and Ocean Rate Advisory — GTOR), conforme pedido pela
Issue #20: "documentar termos, frequência, schema e qualidade antes de
qualquer carga no BigQuery". **Nenhum dado foi carregado no BigQuery nesta
avaliação.**

## Plataforma e acesso

- Domínio: `agtransport.usda.gov`, operado pelo USDA Agricultural Marketing
  Service (AMS), Transportation Services Division.
- Motor: [Socrata Open Data (SODA)](https://dev.socrata.com/), o mesmo
  padrão usado por `data.gov` e vários portais estaduais dos EUA — API REST
  JSON, sem necessidade de autenticação para leitura pública.
- Metadados de um dataset: `GET /api/views/{dataset_id}.json` (schema de
  colunas, licença, atribuição, categoria, timestamp de última atualização).
- Registros: `GET /resource/{dataset_id}.json` com parâmetros SoQL
  (`$select`, `$where`, `$order`, `$limit` até 50000, `$offset`).
- Licença declarada pela API: `None` (sem restrição explícita) em todos os
  datasets avaliados; atribuição consistente como `USDA/AMS/TM/TSD` ou
  `USDA AMS TM TSD`. Trata-se de dado público oficial do governo dos EUA —
  compatível com o uso já feito de outras fontes oficiais no projeto (CONAB,
  ANEEL, ANTT), mas a licença deve ser revalidada por dataset antes de
  qualquer publicação derivada, já que a plataforma não expõe um termo de
  uso único e explícito por API.
- Conectividade real confirmada nesta avaliação (`curl` direto aos
  endpoints acima, e depois via testes automatizados em
  `usda_agtransport/tests/test_datasets_live.py`).

## Datasets avaliados

| Dataset | ID | Cadência | Relevância MT | Observação |
|---|---|---|---|---|
| Grain Transportation Cost Indicators | `8uye-ieij` | semanal | indireta | Índices de custo por modal (caminhão, ferrovia, barcaça, navio) nos EUA, base 2017=100. Contexto global, sem rota brasileira. |
| U.S. vs Brazil Soybean Transportation Cost Spreads | `3j5w-mz4e` | trimestral | direta | Spreads de custo de transporte de soja EUA vs. Brasil até Xangai, incluindo origem `north_mt`. |
| Quarterly Truck Rates for Selected Brazilian Soybean Export Transportation Routes | `wcku-8yrp` | trimestral | direta | Fretes rodoviários por rota nomeada, incluindo rotas com origem `North MT (Sorriso)` até Santos e Paranaguá. **Dataset mais diretamente relevante ao MT encontrado nesta avaliação.** |
| Monthly Brazilian Weighted Average Truck Prices for Exported Soybeans | `i4ty-m7hq` | mensal | direta | Índice nacional agregado de frete rodoviário para soja de exportação (não desagregado por UF). |
| Downbound Grain Barge Rates | `deqi-uken` | semanal | indireta | Fretes de barcaça no sistema fluvial dos EUA. Contexto de escoamento concorrente, sem rota brasileira. |

Este é um subconjunto priorizado (5 de ~110 datasets do catálogo
`agtransport.usda.gov`, filtrados por relevância a soja/MT/Brasil). O
catálogo completo pode ser navegado via
`https://api.us.socrata.com/api/catalog/v1?domains=agtransport.usda.gov`.

### Amostra real — fretes rodoviários Brasil (`wcku-8yrp`)

```json
{"quarter_ending_date":"2025-07-31T00:00:00.000","year_quarter":"2025Q3","year":"2025","quarter":"3",
 "routeno":"2","route":"North MT (Sorriso) - Santos","origin":"North MT (Sorriso)",
 "destination":"Santos","distance_miles":"1190","share":"3.3","rate":"7.74"}
```

Colunas: `quarter_ending_date`, `year_quarter`, `year`, `quarter`, `routeno`,
`route`, `origin`, `destination`, `distance_miles`, `share`, `rate`
(USD/tonelada métrica).

## Classificação de evidência

Seguindo `docs/DATA_GOVERNANCE.md` (dado observado vs. inferência vs.
estimativa vs. informação negociada):

- **Observado/oficial**: `Grain Transportation Cost Indicators`,
  `Downbound Grain Barge Rates`, `Quarterly Truck Rates...` e
  `Monthly Brazilian Weighted Average Truck Prices...` — séries publicadas
  diretamente pelo USDA a partir de pesquisa/coleta própria.
- **Derivado/calculado**: `U.S. vs Brazil Soybean Transportation Cost
  Spreads` — o valor de spread é uma subtração entre duas séries de custo
  publicadas (`*_to_shanghai` menos origem de referência); a série de custo
  em si é observada, mas a coluna de spread é derivada. Qualquer carga
  futura deve preservar as colunas-base e tratar o spread como campo
  calculado, não como observação primária.

## Qualidade e limitações observadas

- Sem chave/token obrigatório para os volumes consultados nesta avaliação;
  `SocrataClient` aceita `app_token` opcional para cenários de maior volume.
- Datas em `calendar_date` (string ISO sem timezone) — precisam de
  normalização explícita de fuso/timezone antes de qualquer comparação com
  séries brasileiras (CONAB, IMEA) que já usam `data_referencia` em UTC-3
  implícito.
- Granularidade geográfica do frete rodoviário brasileiro é por rota
  nomeada (ex. "North MT (Sorriso) - Santos"), não por município/UF
  estruturado — qualquer carga futura precisaria de um mapeamento
  rota→origem/destino próprio do AgroLog, não fornecido pela fonte.
- `Monthly Brazilian Weighted Average Truck Prices` é uma série nacional
  agregada, sem desagregação por UF — não substitui os fretes por rota de
  `wcku-8yrp` para uso específico de MT.
- Nenhuma indicação de descontinuação nos datasets avaliados; `rowsUpdatedAt`
  de `wcku-8yrp` mostra atualização recente (2025Q3 como trimestre mais
  novo no momento desta avaliação).

## Termos de uso

Dado público do governo federal dos EUA (USDA AMS), sem chave de API
obrigatória para os endpoints de leitura usados. Licença declarada pela
API como `None` (ausência de restrição adicional além do domínio público
padrão de obras do governo federal dos EUA). Atribuição a manter em
qualquer uso derivado: `USDA AMS Transportation Services Division /
AgTransport`.

## Código

`usda_agtransport/` — cliente Python somente leitura da API SODA
(`SocrataClient`) e registro dos datasets avaliados (`KNOWN_DATASETS`). Ver
`usda_agtransport/README.md` para uso e testes.

## Próximos passos (não executados nesta avaliação)

1. Definir mapeamento rota→origem/destino estruturado (UF/município) para
   `brazil_soybean_truck_route_rates` antes de qualquer carga no BigQuery.
2. Decidir schema de destino (dataset/tabela) seguindo o mesmo padrão de
   `data_referencia`/`data_publicacao`/`data_coleta`/`competencia` usado
   pelas demais fontes do projeto.
3. Avaliar se `grain_transportation_cost_indicators` e
   `downbound_grain_barge_rates` (referência global/EUA) devem entrar como
   contexto de mercado ou ficar fora do escopo do AgroLog MT.
4. Só então considerar carga real no BigQuery, seguindo o mesmo processo de
   piloto validado usado para CONAB Armazéns.
