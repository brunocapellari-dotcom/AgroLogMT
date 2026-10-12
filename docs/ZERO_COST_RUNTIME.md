# AgroLog Intelligence — ZERO_COST Runtime

## Regra econômica

A Sellable V1 deve possuir um modo operacional que não exija desembolso incremental:

- implantação: **R$ 0**;
- custo recorrente obrigatório: **R$ 0/mês**;
- API paga obrigatória: **nenhuma**;
- banco cloud pago obrigatório: **nenhum**;
- servidor always-on obrigatório: **nenhum**.

`contracts/zero_cost_runtime.v1.json` é o contrato canônico desta regra.

## Arquitetura V1

```text
FONTES PÚBLICAS/GRATUITAS
        |
        v
COLETORES PYTHON
        |
        +--> LocalStore: RAW + manifestos + estado
        |
        v
DUCKDB LOCAL
        |
        +--> PARQUET ZSTD
        |
        v
PROCESSAMENTO / MARTS EM LOTE
        |
        v
COMMERCIAL SNAPSHOT JSON
        |
        v
BUNDLE ESTÁTICO
        |
        v
DASHBOARD ESTÁTICO / RELATÓRIO
```

O GCP continua disponível como backend opcional. BigQuery, Cloud Run, GCS, WIF e serviços associados não são requisitos para executar ou validar o perfil ZERO_COST.

## Persistência

O `collector.storage.LocalStore` é a base do modo gratuito para RAW, manifestos e estado. Artefatos RAW mantêm SHA-256 e caminho temporal. Dados derivados destinados ao cliente são materializados em bundle estático, evitando consulta analítica paga a cada abertura do dashboard.

O banco analítico canônico do perfil ZERO_COST agora é DuckDB, executado como biblioteca embarcada, sem daemon ou servidor. As tabelas analíticas são exportáveis para Parquet com compressão ZSTD. A primeira migração operacional inclui BCB PTAX e MDIC/SECEX ComexStat; os demais domínios permanecem explicitamente como SOURCE_GAP até sua migração, sem preenchimento por inferência silenciosa.

## Execução local

`python scripts/run_zero_cost_pipeline.py` coleta as fontes públicas suportadas, atualiza DuckDB/Parquet e materializa snapshot e relatório. `python scripts/build_zero_cost_outputs.py` reconstrói apenas os produtos estáticos a partir do banco local existente.

## Publicação

`scripts/build_zero_cost_bundle.py` recebe um snapshot comercial já calculado e gera `commercial-snapshot.json` e `zero-cost-manifest.json`, com hash SHA-256 e declaração explícita de que não há runtime pago nem credencial cloud obrigatória.

O artefato pode ser servido por hospedagem estática gratuita, servidor local ou outro canal sem custo. Nenhum fornecedor gratuito específico é dependência canônica.

## Hard stop

Free tier não é sinônimo de custo zero garantido. Portanto:

1. nenhum componente pode habilitar cobrança automática como requisito do ZERO_COST;
2. franquias gratuitas opcionais devem parar/degradar ao atingir o limite;
3. mudança de preço de fornecedor não pode transformar o produto em pago silenciosamente;
4. o perfil local/estático deve continuar funcional sem o fornecedor;
5. credenciais e segredos nunca entram no bundle do navegador.

## GCP

O gate LIVE/GCP existente é preservado para a arquitetura cloud futura. Ele deixa de definir sozinho se a versão ZERO_COST é utilizável. Não remover os conectores GCP: eles são um caminho de escala, não uma dependência econômica da V1.

## Validação

```bash
python scripts/validate_zero_cost_runtime.py
```

Resultado esperado: `status=PASS`, `implementation_cost_ceiling_brl=0`, `recurring_cost_ceiling_brl=0`, `paid_runtime_required=false` e `cloud_credentials_required=false`.

A validação é local, testa LocalStore, DuckDB, Parquet e bundle estático e não realiza chamadas a GCP ou a qualquer serviço pago.

## Operator mode

For routine operation, copy:

`config/zero_cost_operator.example.json`

to:

`config/zero_cost_operator.json`

Then fill only the operational paths and the real market authorization metadata. No Python edit is required.

Run:

`python scripts/run_zero_cost_operator.py --config config/zero_cost_operator.json`

The operator launcher resolves relative paths from the config file directory and calls the canonical ZERO_COST pipeline. The process exits with code 0 only when the commercial report is SELLABLE. If the report is BLOCKED, evidence and output files are still written, but the process exits non-zero so cron/systemd/Windows Task Scheduler can detect the failure.

Required human/operator inputs, when applicable:

- `freight_input`: authorized JSON/JSONL containing individual announced freight records;
- `market_input`: authorized CSV/JSON/JSONL market references;
- `market.source_id`;
- `market.source_name`;
- `market.usage_rights`;
- `market.authorization_basis`.

The launcher does not convert technical access into commercial reuse rights. Market data is rejected unless explicit rights metadata is present.

