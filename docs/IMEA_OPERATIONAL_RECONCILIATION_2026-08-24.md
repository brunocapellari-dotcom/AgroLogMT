# IMEA operacional — reconciliação N6 — 2026-08-24

Fonte analisada: `imea-1.xlsx` existente no Drive do AgroLog MT.
SHA-256 observado: `d916c6b575c99940ad990cd55e568de37fa9e469c23bc1704c2574a23ca9fbf9`.

## Cobertura observada

| Aba | Linhas de dados | Primeiro registro | Último registro |
|---|---:|---|---|
| indicadores diarios | 7.411 | 2023-01-02 | 2026-07-31 |
| indicadores semanais | 1.160 | 2023-01-12 | 2026-07-31 |
| frete | 4.164 | 2023-01-13 | 2026-07-31 |
| semeadura | 190 | 2020-09-18 | 2026-03-20 |
| colheita | 213 | 2021-01-15 | 2026-07-31 |

Total de linhas tabulares: **13.138**.

Nenhuma duplicidade foi encontrada nas chaves naturais testadas das cinco abas. Valores de progresso de semeadura/colheita ficaram dentro de `[0,1]`. Há células regionais ausentes, principalmente para a região Norte em algumas séries; ausência não é convertida em zero.

## Conteúdo

Indicadores diários cobrem soja, milho e algodão, incluindo preço físico, CBOT, PTAX, CEPEA e prêmios portuários. Indicadores semanais incluem farelo/óleo de soja e caroço/torta/óleo de algodão.

Fretes possuem 4.164 observações, 7 origens, 8 destinos e 28 combinações produto/tipo/origem/destino. Destinos incluem Santos, Paranaguá, Rondonópolis, Miritituba, Porto Velho, Uberlândia, Alto Araguaia e Rio Verde.

Semeadura e colheita cobrem as safras 20/21 a 25/26 para soja, milho e algodão, com macrorregiões IMEA e total MT.

## Regra semântica obrigatória

`frete` no workbook é tratado como **referência/indicador de frete publicado pelo IMEA**, não como frete efetivamente negociado ou pago. O parser N6 usa `evidence_subtype=imea_freight_reference` e `negotiated=false`.

Progresso de semeadura e colheita é classificado como estimativa publicada (`evidence_class=estimado`), não medição censitária observada.

## Relação com IMEA Agro v1.2

O workbook operacional não substitui o pacote auditado v1.2. A v1.2 contém 40.190 linhas RAW estruturadas, 40.046 registros confiáveis, 35.848 registros de custos, 3.666 observações O&D e 2.431 observações de estimativas. Portanto, o `imea-1.xlsx` é uma superfície operacional complementar e deve ser reconciliado com o histórico auditado antes de promoção produtiva.

## Promoção

1. parser reprodutível do workbook;
2. QA de chaves, datas, unidades e intervalos;
3. crosscheck com o pacote v1.2;
4. carga append-only em tabelas canônicas;
5. idempotência;
6. inspector/readiness;
7. somente então liberar features para o Data Mart Soja MT.
