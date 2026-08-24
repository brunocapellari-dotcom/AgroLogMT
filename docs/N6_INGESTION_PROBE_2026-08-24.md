# N6 — Evidência do probe de ingestão — 2026-08-24

Este registro documenta o probe read-only executado pelo workflow `probe-n6-ingestion` durante o PR #69. O probe não grava Drive nem BigQuery e não promove nenhuma fonte a produção.

## Política do probe

- regressão de contrato, layout ou semântica: **falha o CI**;
- indisponibilidade externa de rede/TLS: registrada como `unavailable`, sem ser confundida com regressão de código;
- TLS nunca é desativado para fazer um teste passar;
- o artifact JSON é preservado mesmo quando uma fonte externa está indisponível.

## Resultado aprovado

`contract_failures = []`.

### CONAB Safra — histórico

A descoberta viva encontrou 7 publicações consecutivas da safra 2025/26 no momento do teste, do 5º ao 11º levantamento, cada uma com página e XLSX oficial próprio.

Isto comprova no nível de descoberta que o backfill pode preservar cada levantamento como um vintage independente. A carga histórica continua gated pelo P0/P1 e deverá registrar publicação, coleta, hash e safra/levantamento.

### IBGE Localidades

- 142 municípios retornados para Mato Grosso;
- 142 códigos IBGE únicos;
- sentinelas encontradas: Lucas do Rio Verde, Cuiabá, Sorriso e Rondonópolis;
- uma resposta gzip observada no CI levou à correção do transporte HTTP; o cliente agora trata compressão sem decodificar bytes comprimidos como UTF-8.

### NASA POWER

Probe histórico fixo em ponto de Mato Grosso (`lat=-13.05`, `lon=-55.91`) para 2025-01-01 a 2025-01-03:

- 15 observações = 3 dias × 5 parâmetros;
- parâmetros: `PRECTOTCORR`, `RH2M`, `T2M`, `T2M_MAX`, `T2M_MIN`;
- classificação preservada: `estimado` / `nasa_power_gridded`;
- o produto não é apresentado como estação meteorológica observada.

### Comex Stat

O endpoint oficial configurado para NCM exportação 2026 apresentou cadeia TLS incompleta/incompatível no runner GitHub durante o probe. A verificação de certificado **não foi desativada**.

A implementação foi endurecida para:

- HTTPS obrigatório;
- `requests` + trust store/certifi do runtime;
- redirects somente se continuarem HTTPS;
- download streaming;
- SHA-256 incremental;
- validação do cabeçalho em amostra limitada;
- falha fechada em incompatibilidade de layout.

Enquanto a cadeia TLS do host não for validável no runtime produtivo, o endpoint deve permanecer `unavailable` e não pode ser promovido a ingestão produtiva apenas porque o layout está documentado.

## CI

No head que originou este registro:

- `unit-tests`: **success**;
- `probe-n6-ingestion`: **success**;
- nenhum `contract_failure` no artifact;
- indisponibilidade externa do Comex foi registrada separadamente.

## Próximo uso

Esta evidência autoriza o merge do código de preparação da próxima vertical, mas não altera o gate cloud. A sequência continua: homologar núcleo GCP → habilitar CONAB Safra → backfill de vintages → migrar IMEA → homologar Comex no runtime de produção → clima/hidrologia → Data Mart Soja MT.
