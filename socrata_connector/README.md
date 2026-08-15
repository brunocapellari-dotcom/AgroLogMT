# socrata_connector

Cliente Python somente leitura, genérico, para APIs
[SODA (Socrata Open Data)](https://dev.socrata.com/) — a plataforma usada
por vários portais de dados oficiais (ex.: `agtransport.usda.gov`,
`publicreporting.cftc.gov`, `data.gov` e diversos portais estaduais dos
EUA).

Extraído de `usda_agtransport.client` (Issue #20) e `cftc_cot.client`
(Issue #14), que implementavam a mesma lógica de forma duplicada — mesmo
padrão já usado no projeto para `ckan_connector` (Issue #19), que é
consumido por múltiplas fontes CKAN (ANEEL, ANTT).

## O que este módulo faz

- `SocrataClient(base_url, ...)` — cliente apontado para um único host
  declarado em `base_url`. Por padrão só fala com esse host exato
  (`allowed_hosts` pode ser passado explicitamente para permitir mais de
  um, mas o padrão são hosts fixos por instância).
- `SocrataClient.dataset_metadata(dataset_id)` — nome, descrição,
  atribuição, licença, categoria, data de última atualização de linhas e
  schema de colunas (`/api/views/{id}.json`).
- `SocrataClient.query(dataset_id, select=..., where=..., order=..., limit=,
  offset=)` — registros via `/resource/{id}.json`, com paginação
  (`$limit`/`$offset`) e teto de `$limit` alinhado ao limite real da API
  SODA (50000).
- Retries com backoff exponencial em erros de rede e `429`/`5xx`.
- Erros HTTP não-200 ou payload malformado viram `SocrataApiError`; falhas
  de rede/DNS viram a subclasse `SocrataConnectionError`.
- Redirects não são seguidos (`allow_redirects=False`).

## Aviso de segurança — `select`/`where`/`order`

Essas cláusulas são **SoQL literal**, encaminhadas sem sanitização — a API
SODA não oferece parâmetros vinculados para SoQL (diferente do BigQuery,
que tem `ScalarQueryParameter`). Este cliente é seguro apenas quando quem
monta essas cláusulas é código próprio de fonte (ex.: `datasets.py` de cada
módulo consumidor). **Nunca** repasse texto de usuário final diretamente
para `select`/`where`/`order`. Superfícies voltadas a usuário final (ex.:
AgroLog Gateway) devem continuar usando consultas parametrizadas do
BigQuery, não este cliente.

## O que este módulo *não* faz

- Não carrega nada em BigQuery — é só o cliente de leitura da fonte.
- Não requer chave/token: os endpoints públicos usados pelos consumidores
  atuais não exigem autenticação. Um `app_token` opcional (`X-App-Token`)
  pode ser passado para elevar limites de taxa.
- Não descobre catálogo de datasets automaticamente — cada módulo
  consumidor registra os datasets/contratos que já validou (ver
  `cftc_cot.datasets`, `usda_agtransport.datasets`).

## Uso básico

```python
from socrata_connector import SocrataClient

client = SocrataClient(base_url="https://publicreporting.cftc.gov")
metadata = client.dataset_metadata("kh3c-gbw2")
records = client.query(
    "kh3c-gbw2",
    where="market_and_exchange_names = 'SOYBEANS - CHICAGO BOARD OF TRADE'",
    order="report_date_as_yyyy_mm_dd DESC",
    limit=5,
)
```

Módulos consumidores tipicamente expõem uma função `build_client()` já
apontada para o host correto (ver `cftc_cot.client.build_client`), em vez
de expor `base_url` diretamente a quem usa o módulo.

## Testes

```bash
pip install -r socrata_connector/requirements-dev.txt
python -m pytest -q socrata_connector/tests
```

Testes com HTTP mockado (determinístico, sem rede) — cobrem allowlist de
host, tratamento de redirect/erro/payload malformado e montagem de
parâmetros SoQL. Testes de integração real contra uma fonte específica
ficam no módulo consumidor (ex.: `cftc_cot/tests/test_datasets_live.py`).
