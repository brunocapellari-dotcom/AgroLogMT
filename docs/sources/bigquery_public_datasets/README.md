# BigQuery Public Datasets — avaliação (Issue #21)

Avaliação de NOAA GSOD e GDELT v2 nos conjuntos públicos do BigQuery,
conforme pedido pela Issue #21: "custo, atualização e compatibilidade de
localização com o BigQuery do AgroLog MT". **Nenhum dado foi carregado no
BigQuery `logistica` nesta avaliação** — todas as consultas foram
executadas em modo leitura contra os datasets públicos. Os números de
`totalBytesProcessed` abaixo vêm de `bq query --dry_run` (estimativa de
bytes que o job leria, não cobrança monetária efetiva — a cobrança real
depende do preço vigente e do free tier já consumido pelo projeto/conta de
faturamento no mês).

Revisão adversarial via Codex CLI (`codex exec --sandbox read-only`, com
busca web) encontrou 14 problemas reais nesta avaliação antes desta versão
— incluindo uma afirmação de atualização do NOAA GSOD que estava invertida
em relação à evidência real, uma janela de tempo mal rotulada no GDELT e a
omissão de uma opção de compatibilidade de localização (global queries).
Todos foram corrigidos com nova evidência real abaixo.

## Achado: incompatibilidade de localização (parcialmente mitigável)

O dataset `logistica` do AgroLog MT está em `southamerica-east1`
(confirmado via `bq show project-<id>:logistica`). Os dois datasets
públicos avaliados estão em `US` (multi-região):

```
bigquery-public-data.noaa_gsod → location: US
gdelt-bq.gdeltv2               → location: US
```

Por padrão, o BigQuery exige que todas as tabelas referenciadas em um
mesmo job estejam na mesma localização — um `JOIN` direto entre
`logistica.*` e os datasets acima falharia com erro de localização.

Isso deixou de ser uma impossibilidade absoluta: o BigQuery lançou
**global queries** (Preview, confirmado em
[docs.cloud.google.com/bigquery/docs/global-queries](https://docs.cloud.google.com/bigquery/docs/global-queries)),
que permite `JOIN`/`UNION` entre regiões em uma única query, copiando os
dados remotos filtrados para tabelas temporárias que persistem por
**24 horas** na região principal. Requer opt-in explícito do
administrador do projeto (`enable_global_queries_execution` e
`enable_global_queries_data_access`), cobra computação em cada região
tocada mais transferência e armazenamento temporário, e tem limitações
atuais relevantes para este caso concreto: **pseudocolunas como
`_PARTITIONTIME` não podem ser consultadas em global queries** — ou seja,
a poda de partição usada em `sql/gdelt_events_mt_recent.sql` para manter
o custo baixo (~138 MB) não estaria disponível via global query, que
exigiria varrer a tabela remota sem esse filtro (a consulta com
`_PARTITIONTIME`, tal como está, simplesmente falharia via global query,
não executaria como full scan silencioso). Além disso, habilitar
`enable_global_queries_data_access` depende de configuração no projeto
proprietário dos dados remotos (`bigquery-public-data`/`gdelt-bq`), não
apenas do projeto do AgroLog MT — fora do controle direto do
administrador do AgroLog para esses datasets específicos, o que pode
inviabilizar essa via na prática mesmo após decisão interna de adotá-la.
Outras limitações:
colunas `RANGE` não suportadas, nomes de coluna flexíveis incompatíveis,
sem pushdown de otimização para colunas `STRUCT`, máx. 10 tabelas por
região remota, sem cache de query, sem `INFORMATION_SCHEMA` cross-region,
sem view materializada. Nenhuma dessas configurações foi habilitada nesta
avaliação — isso é um levantamento de viabilidade, não uma ativação.

Caminhos possíveis para uso futuro (nenhum implementado nesta avaliação):

1. **Global queries (Preview)** — join direto sob demanda, sem ETL
   próprio, mas com opt-in, limitações de Preview e custo de transferência
   por execução; melhor para exploração pontual, não para pipeline
   recorrente até sair de Preview.
2. Rodar a consulta/agregação contra o dataset público como job em `US`,
   exportar o resultado já filtrado/agregado para Cloud Storage, e
   carregar em `logistica` via job de load — mesmo padrão ETL já usado
   para as demais fontes.
3. Cópia de tabela cross-region via `bq cp` — também em Preview
   ([docs.cloud.google.com/bigquery/docs/managing-tables#copy_tables_across_regions](https://docs.cloud.google.com/bigquery/docs/managing-tables#copy_tables_across_regions)).
   Copia tabela/snapshot/clone inteiro (não o resultado filtrado de uma
   query), cobra transferência e armazenamento, e cancelar o job após
   iniciado não evita a cobrança já incorrida — pouco adequado aqui dado
   o tamanho de GSOD/GDELT como um todo.
4. Consulta direta aos datasets públicos em `US`, sem persistir nada em
   `logistica` — job BigQuery comum na região `US`, útil para exploração
   ad hoc que não precise cruzar com dados do AgroLog na mesma query.

Qualquer carga futura precisa decidir explicitamente por um desses
caminhos antes de implementar — não é um detalhe de configuração trivial.

## NOAA GSOD (`bigquery-public-data.noaa_gsod`)

- Séries diárias de estações meteorológicas globais (temperatura, chuva,
  vento, pressão), uma tabela por ano (`gsod1929` … `gsod2025`), mais
  `stations` (metadados de estação, incluindo lat/lon/elevação/período de
  operação).
- **Cobertura na região de MT**: consulta real a `stations` filtrando
  `country='BR'` e uma bounding box retangular que cobre o território de
  Mato Grosso (`lat BETWEEN -18 AND -7`, `lon BETWEEN -61 AND -50`)
  retornou >50 estações, incluindo CUIABA (`usaf=833610`), MARECHAL RONDON
  — aeroporto de Cuiabá (`usaf=833620`), CAMPO NOVO DOS PARECIS, ALTA
  FLORESTA, entre outras. **Ressalva**: a bounding box retangular não é o
  polígono real do estado — pode incluir estações de estados/países
  vizinhos (ex. Goiás, Bolívia) e não foi validada estação a estação
  contra o limite oficial de MT. Ver `sql/noaa_gsod_stations_mt.sql`.
- **Atualização — achado corrigido**: `MAX(CONCAT(year,mo,da))` sobre a
  tabela `gsod2025` inteira (todas as estações do mundo, não só MT),
  executada de forma real (não dry-run) e versionada em
  `sql/noaa_gsod_max_date_2025.sql`, retorna **2025-08-28** como data mais
  recente disponível — ou seja, o dado mais recente publicado neste
  dataset está com defasagem de aproximadamente **um ano** em relação à
  data desta avaliação (2026-08-15). Isso contradiz uma versão anterior
  deste documento, que havia interpretado incorretamente a simples
  presença de registros de 2025 como "segue sendo atualizado". A tabela
  `gsod2025` existe e tem dados, mas não está corrente. Não foi verificado
  se há uma tabela mais recente com nome diferente (`gsod2026` não existe
  no dataset no momento desta avaliação) nem se a defasagem é uniforme
  entre estações.
- **Bytes estimados (dry-run, consulta exatamente igual à versionada em
  `sql/noaa_gsod_sample_2025.sql`)**: filtrar `gsod2025` por uma única
  estação (`stn = '833620'`) processa **~96 MB** — a tabela anual inteira
  é lida independentemente do filtro de estação, pois não há
  particionamento por estação dentro do ano. O custo escala com o número
  de *tabelas anuais* consultadas, não com o filtro de estação. Nenhum
  custo monetário real foi medido nesta avaliação — apenas bytes
  estimados via `--dry_run`, amplamente dentro do free tier mensal
  (primeiro 1 TB/mês, sujeito ao consumo já feito pelo projeto/conta de
  faturamento) mesmo para várias décadas × várias estações.
- **Licença**: dado do NOAA/NCEI (governo dos EUA), listado no catálogo de
  BigQuery Public Datasets em
  [cloud.google.com/bigquery/public-data](https://cloud.google.com/bigquery/public-data)
  sem termo de uso restritivo adicional além do documentado pela NOAA.

## GDELT v2 (`gdelt-bq.gdeltv2`)

- Eventos globais extraídos de notícias (GDELT Event Database), tabela
  `events_partitioned` particionada por dia (`_PARTITIONTIME`), com colunas
  de atores, tipo de evento (`EventCode`, taxonomia CAMEO), `GoldsteinScale`
  (score de cooperação/conflito, -10 a +10, atribuído por metodologia do
  GDELT — não uma medição direta) e geolocalização do evento
  (`ActionGeo_*`).
- **Atualização confirmada**: consulta real (não dry-run, versionada em
  `sql/gdelt_max_date_recent.sql`) filtrada por partição
  (`_PARTITIONTIME >= '2026-08-13'`) retornou `MAX(SQLDATE) = 20260815` —
  a própria data desta avaliação, com ~392 mil eventos nos últimos 3 dias.
  Este é o dataset mais atualizado dos dois avaliados. A cadência de
  publicação de ~15 minutos é declarada pela documentação do próprio
  GDELT Project; esta avaliação **não mediu** o intervalo entre updates
  dentro do BigQuery, apenas confirmou que a partição do dia da consulta
  já está populada.
- **Relevância na região de MT confirmada, qualidade de entidade
  limitada**: consulta real com janela fechada
  (`_PARTITIONTIME` entre 2026-08-01 e 2026-08-16 exclusivo, cobrindo
  01–15/08/2026, `ActionGeo_CountryCode = 'BR'`, `ActionGeo_Fullname LIKE
  '%Mato Grosso%'`) retornou eventos reais (ex. `"Joao Paulo, Estado de
  Mato Grosso, Brazil"`), mas os nomes de ator são frequentemente
  genéricos (`"COMPANIES"`, `"AUTHORITIES"`, `"INDIGENOUS"`) — típico do
  extrator automático do GDELT, sem desambiguação de entidade própria.
  Útil como *sinal* agregado (ex. contagem de eventos por região/período,
  tendência de `GoldsteinScale`), não como fonte de fato estruturado
  equivalente a CONAB/IMEA.
- **Bytes estimados (dry-run, consulta exatamente igual à versionada em
  `sql/gdelt_events_mt_recent.sql`, janela fechada 01–15/08/2026)**:
  **~138 MB** processados. Nenhum custo monetário real foi medido — apenas
  bytes estimados via `--dry_run`. A redução de bytes vem do filtro em
  `_PARTITIONTIME` (poda de partição, confirmada pela documentação do
  BigQuery); os filtros em `ActionGeo_CountryCode` e `ActionGeo_Fullname`
  reduzem linhas retornadas, mas não há evidência nesta avaliação de que
  reduzam bytes cobrados (dependeria de clustering, não verificado). Uma
  janela sem limite superior (como em uma versão anterior deste
  documento) tem custo crescente a cada execução futura — corrigido para
  janela fechada.
- **Licença**: GDELT Project declara os dados disponíveis para uso
  ilimitado e irrestrito, acadêmico, comercial ou governamental, sem
  cobrança ([gdeltproject.org/about.html](https://www.gdeltproject.org/about.html)).
  Não foi localizado nesta avaliação um documento formal único de licença
  com cláusulas específicas (ex. restrição de uso militar) — qualquer uso
  derivado deve reconfirmar o texto vigente na fonte antes de publicação,
  em vez de assumir os termos descritos aqui como definitivos. Distinta da
  licença de domínio público padrão do governo dos EUA usada por
  NOAA/USDA.

## Classificação de evidência

Seguindo `docs/DATA_GOVERNANCE.md`:

- **Observado**: séries diárias de estação GSOD (temperatura, chuva) —
  medição direta publicada pela NOAA/NCEI. Do registro GDELT, apenas o
  fato de que o pipeline do GDELT Project publicou um registro apontando
  para um artigo de notícia, na data de publicação — isso é observado
  (o registro existe e foi publicado).
- **Inferido**: todo o conteúdo semântico do evento GDELT — inclusive a
  própria identificação de que um "evento" ocorreu, o ator envolvido, o
  `EventCode` (classificação CAMEO) e a geolocalização — é extraído
  automaticamente de texto de notícia pelo pipeline de NLP do GDELT, não
  observado diretamente pelo AgroLog nem por uma fonte oficial
  estruturada; deve ser tratado como inferido, não como fato observado.
  `GoldsteinScale` é adicionalmente um score calculado pela metodologia do
  GDELT a partir do `EventCode` — inferido/estimado sobre uma inferência,
  nunca observado, em qualquer uso futuro.

## Qualidade e limitações observadas

- GSOD: dataset com defasagem de ~1 ano em relação à data corrente (ver
  achado de atualização acima) — inadequado para monitoramento
  quase-tempo-real; mais adequado a análise histórica/climatológica.
- GSOD: unidades no padrão NOAA (temperatura em Fahrenheit, chuva em
  polegadas) — precisam de conversão explícita para uso junto de fontes
  brasileiras (CONAB/IMEA, que usam unidades métricas). Múltiplas estações
  próximas com nomes duplicados (ex. duas entradas "ARAGARCAS") — exige
  desambiguação por `usaf`/`wban`, não por nome.
- GSOD: granularidade é por tabela anual sem particionamento por estação
  ou data — qualquer consulta multi-ano precisa somar o custo de cada
  tabela anual lida.
- GDELT: qualidade de entidade (nomes de ator) é baixa para uso como fato
  estruturado; nomes genéricos de ator seriam inadequados para atribuir
  evento a empresa/organização específica sem validação adicional.
- Ambos exigem tratar o desvio de localização (`US` →
  `southamerica-east1`) descrito acima antes de qualquer integração com
  `logistica.*` — nenhuma das opções listadas é "sem custo/sem decisão".
- Nenhuma das consultas desta avaliação usou `--maximum_bytes_billed`;
  foram executadas manualmente com `--dry_run` primeiro. Qualquer uso
  automatizado futuro (scheduled query, job recorrente) deve fixar
  `maximum_bytes_billed` e uma janela de tempo fechada, seguindo o mesmo
  padrão de controle de custo já usado no AgroLog Gateway
  (`docs/sources/`/`gateway/`).

## Próximos passos (não executados nesta avaliação)

- Nenhuma carga foi implementada, conforme escopo da Issue #21
  ("avaliar", não "integrar").
- Se uma integração futura for priorizada: decidir entre os quatro
  caminhos de compatibilidade de localização listados acima antes de
  desenhar qualquer pipeline. GDELT como sinal agregado (contagem/score
  por região-período, dentro de janela fechada) é mais imediatamente
  utilizável que GSOD, que além de exigir normalização de unidades tem
  ~1 ano de defasagem nesta réplica do BigQuery — reavaliar a defasagem
  antes de qualquer decisão, pois pode variar com o tempo.

## Consultas validadas

Ver `sql/` — todas as consultas citadas nesta avaliação estão versionadas
e são reproduzíveis executando o mesmo texto:

- `noaa_gsod_stations_mt.sql` — cobertura de estações na região de MT.
- `noaa_gsod_sample_2025.sql` — amostra de uma estação (bytes estimados).
- `noaa_gsod_max_date_2025.sql` — evidência real (não dry-run) da
  defasagem de ~1 ano.
- `gdelt_events_mt_recent.sql` — eventos MT em janela fechada (bytes
  estimados).
- `gdelt_max_date_recent.sql` — evidência real (não dry-run) de
  atualização até a data corrente.
