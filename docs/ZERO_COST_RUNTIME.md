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

Para volumes maiores, DuckDB/Parquet pode ser adicionado como motor local sem alterar a regra econômica. Ele não é requisito deste primeiro corte.

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

A validação é local e não realiza chamadas a GCP ou a qualquer serviço pago.
