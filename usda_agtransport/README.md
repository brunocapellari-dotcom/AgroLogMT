# usda_agtransport

Cliente somente leitura para a API SODA (Socrata) da plataforma
[Open Ag Transport Data](https://agtransport.usda.gov/) do USDA AMS.

Implementa a avaliação/PoC pedida pela Issue #20 — descoberta de schema,
cadência e qualidade dos datasets GTR/GTOR/AgTransport antes de qualquer
carga no BigQuery, evitando reescrever a cada dataset a mesma lógica de
metadados e consulta.

## O que este módulo faz

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
- Só fala com `https://agtransport.usda.gov`: `base_url` aceita apenas hosts
  em uma allowlist fixa (`_ALLOWED_HOSTS`), e redirects não são seguidos
  (`allow_redirects=False`) — um `3xx` inesperado vira `SocrataApiError` em
  vez de ser seguido para outro host. Diferente do conector CKAN
  (Issue #19), este módulo não segue URLs de recursos vindas de um catálogo
  remoto; a única superfície de rede é a chamada direta ao host permitido.

## O que este módulo *não* faz

- Não carrega nada no BigQuery. Isso é intencional: a Issue #20 pede
  avaliação de termos, frequência, schema e qualidade antes de qualquer
  decisão de carga.
- Não requer chave/token: os endpoints usados são de leitura pública. Um
  `app_token` opcional (`X-App-Token`) pode ser passado para elevar limites
  de taxa, mas não é necessário para volumes pequenos de consulta.

## Datasets avaliados

Ver `datasets.py` (`KNOWN_DATASETS`) e
`docs/sources/usda_agtransport/README.md` para a avaliação completa
(cadência, schema, relevância para MT, evidência).

## Uso básico

```python
from usda_agtransport import SocrataClient, KNOWN_DATASETS

client = SocrataClient()
config = KNOWN_DATASETS["brazil_soybean_truck_route_rates"]

metadata = client.dataset_metadata(config.dataset_id)
print([c.field_name for c in metadata.columns])

records = client.query(config.dataset_id, where="origin like '%MT%'", limit=10)
```

## Testes

```bash
pip install -r usda_agtransport/requirements-dev.txt
python -m pytest -q usda_agtransport/tests
```

`tests/test_client.py` usa HTTP mockado (determinístico, sem rede).
`tests/test_datasets_live.py` faz chamadas reais à API AgTransport/USDA e
usa `pytest.skip` automaticamente se a plataforma estiver inacessível no
ambiente — não falha o build por indisponibilidade externa. Um dos testes é
uma regressão de relevância: confirma que o dataset de fretes rodoviários
brasileiros continua tendo pelo menos uma rota com origem no MT.
