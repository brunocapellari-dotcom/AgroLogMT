# Execução contínua — Drive + BigQuery + Cloud Run Jobs

Esta etapa conecta o motor `collector/` a uma execução persistente. Ela complementa a Issue #36: n8n pode orquestrar os jobs, mas a lógica de coleta permanece no código.

## Arquitetura

`Cloud Scheduler/n8n -> Cloud Run Job -> CollectorEngine -> Google Drive (RAW) + BigQuery (state/manifests)`

Frequências alvo:
- Radar: a cada 2 horas;
- Dados: a cada 4 horas;
- Conhecimento: a cada 1 hora.

## Persistência

- Google Drive: artefatos RAW por `RAW/<grupo>/<source_id>/AAAA/MM/DD/<sha256>.<ext>`;
- BigQuery `agrolog_ops.collector_source_state`: último estado/hash por fonte;
- BigQuery `agrolog_ops.collector_runs`: manifesto de cada execução.

O hash SHA-256 impede que um artefato idêntico seja gravado novamente.

## Pré-requisitos

1. Service account do coletor com BigQuery Job User + Data Editor (ou permissões mínimas equivalentes no dataset).
2. Service account do Cloud Scheduler com permissão de executar os Cloud Run Jobs.
3. Pasta raiz no Google Drive compartilhada como Editor com a service account do coletor.
4. `gcloud` autenticado no projeto correto.

## Deploy

```bash
export PROJECT_ID="..."
export REGION="southamerica-east1"
export COLLECTOR_SERVICE_ACCOUNT="agrolog-collector@${PROJECT_ID}.iam.gserviceaccount.com"
export SCHEDULER_SERVICE_ACCOUNT="agrolog-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
export DRIVE_FOLDER_ID="..."

bash scripts/deploy_collectors_gcloud.sh
```

O script habilita APIs, cria Artifact Registry se necessário, constrói a imagem, cria/atualiza os três Cloud Run Jobs e os três agendamentos.

## Piloto

A configuração inicial contém quatro fontes pequenas para validar o ciclo completo:
- MAPA SIPEAGRO Alimentação Animal (Dados, CKAN/CSV);
- catálogo ANTT Dados Abertos (Dados, API/JSON);
- CONAB Notícias (Radar, HTML RAW);
- OpenAlex (Conhecimento, API/JSON).

O objetivo é validar execução, Drive, BigQuery, idempotência e logs antes de importar o catálogo completo.

## Limites desta etapa

- Radar ainda preserva HTML RAW; análise semântica/notícia estruturada entra no parser específico.
- Conhecimento ainda preserva descoberta RAW; a nota Markdown Obsidian precisa do pipeline de triagem/síntese.
- PDF/XLSX/CSV ficam no Drive quando a fonte expõe o artefato diretamente; parsing em planilha temática/BigQuery é responsabilidade do normalizador da fonte.
- Detecção de lacuna já existe no núcleo, mas a alimentação automática das referências observadas por fonte será integrada aos normalizadores.
