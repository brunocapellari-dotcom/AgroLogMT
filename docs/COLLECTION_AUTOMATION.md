# Automacao de Coleta — AgroLog MT

Este documento descreve o componente executavel da Frente A definida em `docs/ARCHITECTURE.md` e `docs/BACKLOG.md`.

## Objetivo

Executar fontes heterogeneas sem misturar aquisicao, RAW, normalizacao, qualidade, BigQuery e Obsidian.

## Fluxo operacional em 16 etapas

1. **Catalogo de fonte** — cada fonte possui `source_id`, grupo, metodo, frequencia e metadados.
2. **Scheduler externo** — Radar 2h; Dados 4h; Conhecimento em descoberta continua, respeitando limites da infraestrutura.
3. **Pre-check** — valida fonte habilitada e configuracao sem segredo.
4. **Aquisicao** — preferencia `HTTP/API/arquivo -> Crawl4AI -> Playwright -> browser-use`.
5. **Hash** — SHA-256 do artefato/resposta para idempotencia.
6. **Persistencia RAW** — artefato original fora do GitHub.
7. **Manifesto** — URL, timestamps, hash, tamanho, tipo, versao do coletor e status.
8. **Deteccao de mudanca** — artefato identico nao e duplicado.
9. **Extracao/normalizacao** — componente especifico posterior ao RAW.
10. **Quatro datas** — preservar `data_referencia`, `data_publicacao`, `data_coleta`, `competencia`.
11. **Qualidade** — contagens, duplicidade, ausentes, unidades, anomalias e schema.
12. **Auditoria temporal** — comparar referencias observadas com frequencia esperada.
13. **Backfill** — lacunas viram fila explicita; ausencia de publicacao nao vira zero.
14. **BigQuery** — publicar somente apos validacao, mantendo idempotencia/linhagem.
15. **Drive/Obsidian** — PDF/XLS/CSV autorizados no RAW; conhecimento gera nota Markdown preparada para o vault.
16. **Observabilidade** — manifestos, alertas de falha/lacuna, atraso e resultado de cada execucao.

## O que esta implementado nesta primeira versao

- contratos de fontes e manifestos;
- HTTP/API e resolucao de recurso CKAN;
- RAW local/configuravel;
- SHA-256 e idempotencia;
- estado por fonte;
- manifestos por execucao, inclusive falhas;
- auditor de lacunas diaria, dia util, semanal e mensal;
- CLI para executar uma fonte/grupo e para auditar lacunas;
- testes artificiais do nucleo deterministico.

## Execucao local

```bash
python -m collector.cli run \
  --config collector/config/sources.example.json \
  --root /caminho/fora/do/repositorio/agrolog_raw
```

Somente Dados:

```bash
python -m collector.cli run --config collector/config/sources.example.json --group dados
```

Auditoria de lacunas:

```bash
python -m collector.cli audit-gaps \
  --observed observed.json \
  --start 2026-08-01 \
  --end 2026-08-31 \
  --frequency business_daily
```

## Persistencia em producao

`LocalStore` e deliberadamente simples. A proxima evolucao deve implementar stores/adapters para:

- Google Drive ou Cloud Storage para RAW;
- BigQuery para tabelas normalizadas e logs analiticos;
- pasta `Obsidian` no Drive como estagio de notas Markdown quando o vault local nao estiver montado.

Credenciais devem vir de Secret Manager/ADC/variaveis seguras; nunca de arquivos versionados.

## Scheduler

As tarefas do ChatGPT servem para monitoramento e orquestracao conversacional, mas nao substituem o scheduler do ETL. Para coleta de producao, usar Cloud Scheduler/Cloud Run Jobs (ou mecanismo aprovado equivalente) chamando o mesmo motor configurado por fonte.

## Limite atual

Esta versao nao declara carga em BigQuery, upload no Drive ou sincronizacao no Obsidian. Esses passos so devem ser marcados como concluidos quando o conector real estiver implementado, executado e validado.
