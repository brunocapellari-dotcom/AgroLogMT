# AgroLog Gateway — primeira consulta

Implementação mínima da Issue #13 para consultar **somente leitura** a view canônica de CONAB Armazéns no BigQuery.

## Fonte analítica

`<GOOGLE_CLOUD_PROJECT>.logistica.vw_armazens_atuais`

O projeto e a localização não são hardcoded. O runtime lê:

- `GOOGLE_CLOUD_PROJECT` — obrigatório;
- `BQ_LOCATION` — obrigatório;
- `AGROLOG_BQ_DATASET` — opcional, padrão `logistica`;
- `AGROLOG_ARMAZENS_VIEW` — opcional, padrão `vw_armazens_atuais`;
- `AGROLOG_GATEWAY_MAX_BYTES_BILLED` — opcional, padrão `100000000` bytes.

## Contrato HTTP

### `GET /healthz`

Não acessa BigQuery. Serve para health check do Cloud Run.

### `GET /v1/armazens`

Filtros permitidos:

- `uf` — sigla de duas letras;
- `municipio` — correspondência exata sem diferenciar maiúsculas/minúsculas;
- `identificacao_armazem` — correspondência exata;
- `limit` — 1 a 500, padrão 100;
- `offset` — inteiro não negativo.

O cliente **não envia SQL**. Todos os valores de filtro usam parâmetros BigQuery.

A resposta contém `meta` e `data`. `meta.classification` é `observado`, pois a consulta expõe o estado atual derivado do snapshot CONAB validado, sem inferência do Gateway.

## Segurança

O serviço deve permanecer privado no Cloud Run durante o piloto.

A service account de runtime deve ter somente o necessário:

1. permissão para criar jobs BigQuery no projeto de execução, normalmente via `roles/bigquery.jobUser`;
2. leitura do dataset/view `logistica`, preferencialmente via `roles/bigquery.dataViewer` no menor escopo possível;
3. nenhuma permissão de escrita, edição ou administração do BigQuery.

Não usar chaves JSON de service account dentro do container. Cloud Run deve usar identidade de runtime.

## Limite de custo

Cada consulta define `maximum_bytes_billed`. O padrão desta primeira versão é 100 MB e pode ser reduzido após medir a view real.

## Testes locais

A partir da raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r gateway/requirements-dev.txt
pytest -q gateway/tests
```

No Windows PowerShell, ativar a virtualenv conforme o ambiente local antes de executar `pip` e `pytest`.

## Execução local

```bash
export GOOGLE_CLOUD_PROJECT=<projeto>
export BQ_LOCATION=<localizacao>
uvicorn gateway.main:app --host 127.0.0.1 --port 8080
```

Teste:

```bash
curl 'http://127.0.0.1:8080/v1/armazens?uf=MT&limit=10'
```

## Cloud Run

O diretório `gateway/` contém Dockerfile próprio e pode ser usado como contexto de build/deploy.

Requisitos de implantação:

- região escolhida explicitamente;
- `GOOGLE_CLOUD_PROJECT` e `BQ_LOCATION` configurados no serviço;
- service account dedicada com mínimo privilégio;
- **não permitir acesso anônimo** nesta fase;
- validar manualmente `healthz` e uma consulta de MT antes de qualquer automação.

## Fora do escopo

- escrita no BigQuery;
- SQL arbitrário;
- demais fontes;
- Scheduler;
- autenticação pública complexa;
- sincronização de números para o Obsidian.

## Dependência

Esta implementação parte da view e da validação do piloto CONAB Armazéns presente na PR #12. Ela não cria schema, tabela ou view concorrente.
