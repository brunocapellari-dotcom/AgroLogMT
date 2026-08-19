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
- `roles/bigquery.user` ao coletor, suficiente para jobs e criação do dataset operacional;
- `roles/run.invoker` à conta usada pelo Cloud Scheduler para executar os Cloud Run Jobs.

## Deploy simplificado

Na raiz do repositório:

```bash
bash scripts/deploy_collectors_gcloud.sh
```

Por padrão, o script usa:
- região `southamerica-east1`;
- dataset `agrolog_ops`;
- pasta Drive `AGROLOG MT/07_AUTOMACAO` (`17AX2iCrQ17Jm86Pp9ijqn3hyEHVaQPqd`);
- service accounts `agrolog-collector` e `agrolog-scheduler`.

O script habilita as APIs necessárias, cria contas de serviço, Secret Manager, Artifact Registry, constrói a imagem, cria/atualiza os Cloud Run Jobs e os agendamentos.

## Segredos de APIs externas

Credenciais e chaves não entram no GitHub, no JSON de fontes, em URLs observadas ou arquivos RAW. O deploy usa Google Secret Manager e concede `roles/secretmanager.secretAccessor` somente à service account do coletor.

Secrets do grupo `dados`:
- `agrolog-ana-identificador` -> `ANA_IDENTIFICADOR`;
- `agrolog-ana-senha` -> `ANA_SENHA`;
- `agrolog-api-data-gov-key` -> `DATA_GOV_API_KEY`.

Na primeira execução, se um secret ainda não tiver versão habilitada, o script solicita o valor no terminal de forma oculta. Depois, reutiliza o Secret Manager sem pedir novamente.

## ANA HidroWebService

O grupo `dados` inclui o conector para a API oficial HidroWebService da ANA. A implementação usa a rota de autenticação `EstacoesTelemetricas/OAUth/v1` e a rota `EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1`, com janela de consulta de até 30 dias por requisição.

Estações iniciais do Arco Norte:
- Porto Velho — 15400000;
- Humaitá — 15630000;
- Itacoatiara — 16030000;
- Itaituba — 17730000;
- Santarém — 17900000.

O token é reutilizado em memória por até 55 minutos dentro do mesmo processo.

## USDA FAS Open Data / api.data.gov

A chave `api.data.gov` do projeto é injetada apenas no runtime como `DATA_GOV_API_KEY` e enviada no header `X-Api-Key`, evitando segredo em URL, manifesto ou log.

O primeiro uso é o USDA Foreign Agricultural Service Open Data, que expõe três famílias de dados:
- **PSD** — Production, Supply and Distribution: produção, consumo, comércio, estoques e demais atributos de oferta e demanda mundial;
- **ESR** — Export Sales Report: vendas semanais de exportação dos Estados Unidos;
- **GATS** — Global Agricultural Trade System: comércio exterior Census/UN Trade.

O lote inicial coleta endpoints leves de catálogo e controle de atualização:
- PSD commodities;
- PSD countries;
- PSD commodity attributes;
- ESR commodities;
- ESR data release dates;
- GATS Census export data release dates;
- GATS Census import data release dates.

A estratégia é usar os `dataReleaseDates` para detectar publicação ou revisão e só então disparar cargas maiores. Depois da primeira execução real, serão criadas specs por commodity para soja, milho, algodão e demais produtos priorizados, com histórico e revisões preservados.

## Passo manual do Drive

O Google Cloud IAM não concede acesso ao My Drive. Após a criação da service account do coletor, compartilhe a pasta `07_AUTOMACAO` como Editor com:

`agrolog-collector@<PROJECT_ID>.iam.gserviceaccount.com`

Depois execute:

```bash
gcloud run jobs execute agrolog-dados --region southamerica-east1 --wait
```

Valide:
- Drive: `07_AUTOMACAO/RAW/dados/ana_hidroweb_*/...`;
- Drive: `07_AUTOMACAO/RAW/dados/usda_fas_*/...`;
- BigQuery: `agrolog_ops.collector_runs`;
- BigQuery: `agrolog_ops.collector_source_state`.

## Piloto

A configuração contém fontes pequenas para validar o ciclo completo:
- MAPA SIPEAGRO Alimentação Animal;
- catálogo ANTT Dados Abertos;
- ANA HidroWebService para cinco estações do Arco Norte;
- USDA FAS PSD/ESR/GATS em catálogos e release dates;
- CONAB Notícias;
- OpenAlex.

## Limites desta etapa

- A API ANA é coletada inicialmente como JSON RAW auditável; normalização dos registros e atualização automática da planilha entram após validar a primeira resposta real.
- Cada chamada ANA da série adotada cobre no máximo 30 dias.
- A integração USDA atual prepara aquisição, catálogo e detecção de atualização; carga histórica completa por commodity e normalizadores PSD/ESR/GATS entram após validar a chave no Cloud Run.
- Radar ainda preserva HTML RAW; análise semântica entra no parser específico.
- Conhecimento ainda preserva descoberta RAW; a nota Markdown Obsidian precisa do pipeline de triagem/síntese.
- PDF/XLSX/CSV ficam no Drive quando a fonte expõe o artefato diretamente; parsing em planilha temática/BigQuery é responsabilidade do normalizador da fonte.
