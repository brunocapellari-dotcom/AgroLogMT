# N6 — Loaders canônicos: referência, clima e comércio exterior

## Estado

Código pronto para homologação, **sem execução GCP nesta etapa**.

## IBGE Localidades

Destino: `referencia.municipios_ibge`.

- snapshot preservado;
- `record_id` determinístico pelo conteúdo da dimensão;
- código IBGE é chave geográfica principal;
- view `v_municipios_ibge_latest` seleciona o último snapshot;
- cluster por UF, código IBGE e snapshot;
- classe de evidência: `observado`.

Objetivo: impedir joins por nome livre de município quando existir código oficial.

## NASA POWER

Destino: `clima.nasa_power_daily`.

- partição por `data_referencia`;
- latitude/longitude preservadas;
- parâmetro, valor e unidade preservados;
- `evidence_class=estimado` e `evidence_subtype=nasa_power_gridded` permanecem visíveis;
- view latest resolve a observação mais recente por data × ponto × parâmetro sem apagar vintages.

O loader não transforma NASA POWER em observação de estação.

## Comex Stat

Destinos separados conforme o contrato:

- `comercio_exterior.comexstat_ncm_export`;
- `comercio_exterior.comexstat_ncm_import`;
- `comercio_exterior.comexstat_municipio_sh4_export`;
- `comercio_exterior.comexstat_municipio_sh4_import`.

### Regras

- arquivo anual é normalizado por streaming para NDJSON; não é materializado integralmente em RAM;
- carga BigQuery usa load job para staging, não milhares de inserts individuais;
- staging é deduplicado apenas para linhas **exatamente idênticas** pelo `record_id`; divergências não são apagadas;
- histórico é preservado por `snapshot_id` + `record_id`;
- partição por competência mensal;
- NCM permanece string de 8 dígitos e SH4 string de 4 dígitos;
- `SG_UF_NCM` mantém semântica de UF do produto conforme a base NCM;
- `SG_UF_MUN`/`CO_MUN` mantêm semântica de domicílio fiscal do declarante;
- `CO_URF` continua identificado como Unidade da Receita Federal e **não vira porto físico**;
- `KG_LIQUIDO` e `VL_FOB` são observados; toneladas e USD/t são derivados.

## Gate produtivo

Os loaders não autorizam carga por si sós. Antes de produção:

1. homologar P0/P1 no GCP real;
2. preservar RAW e hash da fonte;
3. validar schema físico BigQuery;
4. executar primeira carga;
5. repetir snapshot idêntico e comprovar idempotência;
6. reconciliar totais com a fonte oficial;
7. registrar evidência de QA no estado N6.
