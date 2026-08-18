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

## Pré-requisitos mínimos

1. `gcloud` autenticado no projeto correto.
2. Permissão do usuário para habilitar APIs, criar contas de serviço, implantar Cloud Run Jobs e criar Cloud Scheduler.
3. Após o script criar a service account `agrolog-collector`, compartilhar a pasta `AGROLOG MT/07_AUTOMACAO` como Editor com o e-mail exibido pelo script.

O script cria automaticamente as duas contas de serviço do piloto quando ausentes e concede:
- `roles/bigquery.user` ao coletor, suficiente para jobs e criação do dataset operacional; o criador passa a controlar o dataset criado;
- `roles/run.invoker` à conta usada pelo Cloud Scheduler para executar os Cloud Run Jobs.

## Deploy simplificado

Se o projeto correto já estiver selecionado no `gcloud`, basta executar na raiz do repositório:

```bash
bash scripts/deploy_collectors_gcloud.sh
```

Por padrão, o script usa:
- região `southamerica-east1`;
- dataset `agrolog_ops`;
- pasta Drive `AGROLOG MT/07_AUTOMACAO` (`17AX2iCrQ17Jm86Pp9ijqn3hyEHVaQPqd`);
- service accounts `agrolog-collector` e `agrolog-scheduler`.

Todos esses valores podem ser sobrescritos por variáveis de ambiente.

O script habilita APIs, cria contas de serviço quando necessário, configura permissões, cria Artifact Registry, constrói a imagem, cria/atualiza os três Cloud Run Jobs e os três agendamentos.

## Passo manual do Drive

O Google Cloud IAM não concede acesso ao My Drive. Após a criação da service account do coletor, compartilhe a pasta `07_AUTOMACAO` como Editor com:

`agrolog-collector@<PROJECT_ID>.iam.gserviceaccount.com`

Depois execute um teste manual:

```bash
gcloud run jobs execute agrolog-dados --region southamerica-east1 --wait
```

Valide:
- Drive: `07_AUTOMACAO/RAW/...`;
- BigQuery: `agrolog_ops.collector_runs`;
- BigQuery: `agrolog_ops.collector_source_state`.

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
