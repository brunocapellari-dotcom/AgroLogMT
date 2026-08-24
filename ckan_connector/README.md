# ckan_connector

Conector genérico de descoberta e download para portais de dados abertos que
expõem a API padrão do [CKAN](https://docs.ckan.org/en/latest/api/) (ANEEL
Dados Abertos, ANTT Dados Abertos e outros portais oficiais equivalentes).

Implementa a Issue #19 — evita reescrever, para cada novo portal CKAN, a
mesma lógica de listar datasets, ler metadados de recursos, baixar arquivos
com retries e registrar hash/tamanho/data de coleta.

## O que este módulo faz

- `CkanClient.package_list()` — lista os identificadores de todos os datasets
  (`package_list` da API CKAN).
- `CkanClient.list_resources(package_id)` — metadados dos recursos
  (arquivos) de um dataset, via `package_show`.
- `CkanClient.download_resource(resource, dest_dir)` — baixa um recurso em
  streaming e devolve um `DownloadRecord` com SHA-256, tamanho em bytes,
  `content_type` e `collected_at` (UTC, ISO 8601).
- Retries com backoff exponencial (via `urllib3.util.retry.Retry`) em erros
  de rede e respostas `429`/`5xx`.
- Erros da API CKAN (`success: false`), HTTP não-200 ou payload malformado
  viram `CkanApiError` (falhas de rede/DNS viram a subclasse
  `CkanConnectionError`, para quem quiser diferenciar "portal fora do ar"
  de "erro de contrato").
- Guarda de segurança em cada requisição (inclusive redirects, seguidos
  manualmente até 5 saltos): exige `https` e recusa hosts óbvios de
  loopback/rede interna (`UnsafeUrlError`). Isto **não** é uma defesa
  completa contra SSRF via DNS rebinding — é suficiente para o modelo de
  ameaça de um conector que só fala com os portais listados em
  `portals.py`, não uma allowlist de rede.
- Limite de tamanho de download (`max_download_bytes`, padrão 500 MB),
  verificado via `Content-Length` quando declarado e sempre durante o
  streaming.
- Escrita atômica: cada download vai para um arquivo temporário exclusivo
  em `dest_dir` e só é promovido (`os.replace`) ao caminho final depois de
  completar dentro do limite; uma falha no meio do download nunca deixa
  arquivo parcial no caminho definitivo nem apaga uma coleta anterior.

## O que este módulo *não* faz

- Não conhece regras específicas de nenhuma fonte (parsing de colunas,
  schema, mapeamento para tabelas do BigQuery). Isso continua sendo
  responsabilidade de código próprio de cada fonte, integrado
  especificamente por dataset/schema — este conector só resolve a camada
  genérica de descoberta/download.
- Não requer nem aceita credenciais: os portais em `portals.py` são
  catálogos públicos sem autenticação.

## Portais validados

Ver `portals.py` (`KNOWN_PORTALS`). Novos portais só devem ser adicionados
depois de validados manualmente (dataset de teste baixado com sucesso),
conforme o critério de aceite da Issue #19.

## Uso básico

```python
from pathlib import Path
from ckan_connector import CkanClient, KNOWN_PORTALS

portal = KNOWN_PORTALS["aneel"]
client = CkanClient(portal.base_url)

packages = client.package_list()
resources = client.list_resources(packages[0])
if resources:
    record = client.download_resource(resources[0], Path("/tmp/ckan_downloads"))
    print(record.sha256, record.size_bytes, record.collected_at)
```

## Testes

```bash
pip install -r ckan_connector/requirements-dev.txt
pytest -q ckan_connector/tests
```

`tests/test_client.py` usa HTTP mockado (determinístico, sem rede).
`tests/test_portals_live.py` faz chamadas reais a ANEEL e ANTT e usa
`pytest.skip` automaticamente se o portal estiver inacessível no ambiente —
não falha o build por indisponibilidade externa.
