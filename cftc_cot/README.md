# cftc_cot

Avaliação da API SODA (Socrata) do
[CFTC Public Reporting](https://publicreporting.cftc.gov/), especificamente
o relatório **Commitments of Traders (COT) — Disaggregated, Combined**
(`kh3c-gbw2`), filtrado para os contratos padrão de soja e milho da CBOT.
O cliente Socrata genérico vive em `socrata_connector/` (ver nota abaixo);
este módulo só tem o que é específico do CFTC.

Implementa o subconjunto sem exigência de chave nova da Issue #14
("Integrar fontes oficiais de mercado agrícola dos EUA"): entre as quatro
fontes aprovadas pela Issue (USDA FAS Open Data, USDA NASS Quick Stats,
USDA AMS MyMarketNews, CFTC Commitments of Traders), apenas o CFTC COT
respondeu sem exigir registro de API key nesta avaliação. Ver
`docs/sources/cftc_cot/README.md` para a avaliação completa, incluindo por
que as outras três ficam bloqueadas por credencial nesta rodada.

## O que este módulo faz

- `build_client(...)` — `socrata_connector.SocrataClient` já travado no
  host oficial `https://publicreporting.cftc.gov` (não aceita `base_url`
  como parâmetro, então não há como apontar acidentalmente para outro
  host).
- `datasets.py` (`KNOWN_CONTRACTS`, `DISAGGREGATED_COMBINED_DATASET_ID`) —
  registro dos contratos e do dataset já validados nesta avaliação.

## O que este módulo *não* faz

- Não carrega nada no BigQuery. Avaliação de termos, cadência, schema e
  qualidade antes de qualquer decisão de carga.
- Não requer chave/token: os endpoints usados são de leitura pública. Um
  `app_token` opcional (`X-App-Token`) pode ser passado para elevar limites
  de taxa, mas não é necessário para volumes pequenos de consulta.
- Não cobre USDA FAS Open Data, NASS Quick Stats nem AMS MyMarketNews —
  todos exigem registro de API key nesta avaliação e ficam fora do escopo
  de "fontes sem bloqueio humano" desta rodada.
- Não reimplementa o cliente Socrata genérico — ver
  `socrata_connector/README.md`.

## Relação com `socrata_connector` e `usda_agtransport`

O cliente Socrata genérico (allowlist de host, retries, metadados e query
SoQL) é canônico em `socrata_connector/`, no mesmo princípio de
`ckan_connector`. `cftc_cot` consome esse pacote para o host CFTC e
`usda_agtransport/client.py` usa um adapter fino sobre a mesma implementação
para o host oficial `agtransport.usda.gov`. Assim, CFTC e USDA compartilham
uma única responsabilidade de transporte SODA sem duplicar cliente HTTP.

## Datasets/contratos avaliados

Ver `datasets.py` (`KNOWN_CONTRACTS`) e
`docs/sources/cftc_cot/README.md` para a avaliação completa (cadência,
schema, relevância para MT, evidência).

## Uso básico

```python
from cftc_cot import build_client, KNOWN_CONTRACTS, DISAGGREGATED_COMBINED_DATASET_ID

client = build_client()
config = KNOWN_CONTRACTS["soybeans_cbot"]

metadata = client.dataset_metadata(DISAGGREGATED_COMBINED_DATASET_ID)
print([c.field_name for c in metadata.columns])

records = client.query(
    DISAGGREGATED_COMBINED_DATASET_ID,
    where=f"market_and_exchange_names = '{config.market_and_exchange_names}'",
    order="report_date_as_yyyy_mm_dd DESC",
    limit=5,
)
```

`select`/`where`/`order` são SoQL literal sem sanitização — ver o aviso de
segurança em `socrata_connector/README.md` antes de repassar qualquer
entrada de usuário final para esses parâmetros.

## Testes

```bash
pip install -r socrata_connector/requirements-dev.txt -r cftc_cot/requirements-dev.txt
python -m pytest -q socrata_connector/tests cftc_cot/tests
```

`socrata_connector/tests/test_client.py` cobre o comportamento genérico do
cliente (HTTP mockado, determinístico, sem rede). `cftc_cot/tests/test_client.py`
cobre só o que é específico daqui (host travado no CFTC).
`tests/test_datasets_live.py` faz chamadas reais à API do CFTC Public
Reporting e usa `pytest.skip` automaticamente, em toda chamada de rede, se
a plataforma estiver inacessível no ambiente — não falha o build por
indisponibilidade externa. Inclui regressão de cadência semanal e de
relevância (contrato padrão de soja continua com open interest muito maior
que o "mini", em vez de um limiar absoluto).
