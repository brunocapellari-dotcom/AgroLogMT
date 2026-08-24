# Geopolitical Watch — Monitor Global de Conflitos

## Objetivo

O Geopolitical Watch e o modulo do AgroLog MT para acompanhar conflitos armados, escaladas militares e choques geopoliticos que possam alterar energia, fertilizantes, comercio, shipping, agricultura ou logistica.

Ele nao e uma fonte de inteligencia militar autoritativa. O modulo agrega sinais publicos, preserva a origem e diferencia explicitamente evento codificado por base de pesquisa, relatorio curado e sinal OSINT/noticioso.

O caso de uso AgroLog e economico/logistico: detectar cedo eventos que possam afetar, por exemplo, petroleo e diesel, fertilizantes, frete maritimo, portos, rotas de comercio, cambio e commodities. O modulo nao transforma uma noticia isolada em fato confirmado e nao transforma um score de triagem em probabilidade de guerra.

## Encaixe na arquitetura existente

Fluxo do MVP:

```text
Fontes publicas / autorizadas
        |
        v
collector/adapters.py
        |
        v
RAW + manifest + hash + data_coleta
        |
        v
collector/geopolitical.py
  - normalizacao
  - classificacao da evidencia
  - deduplicacao/correlacao
  - inferencia de impacto AgroLog
  - score de prioridade
        |
        v
normalized/geopolitical/*.jsonl
        |
        +--> BigQuery (fase posterior aos gates do nucleo)
        +--> AgroLog Gateway
        +--> mapa/dashboard/alertas
        +--> Segundo Cerebro para eventos historicos consolidados
```

BigQuery continua sendo a fonte de verdade analitica. RAW preserva os artefatos coletados. GitHub guarda apenas codigo, contratos, configuracao sem segredo, testes e documentacao.

## Hierarquia de evidencia

### `research_coded`

Eventos codificados por uma base de pesquisa especializada, como UCDP. A existencia do registro na base e observada; ainda assim, revisoes metodologicas e atualizacoes posteriores podem ocorrer.

### `curated_report`

Relatorio ou evento curado por fonte institucional/humanitaria. Exemplo futuro: ReliefWeb/OCHA com appname aprovado.

### `osint_signal`

Noticia, feed ou outro sinal OSINT. O fato observado e que aquela publicacao/sinal foi capturado. O conteudo nao e automaticamente tratado como fato confirmado.

Esta classificacao complementa, sem substituir, `classe_evidencia` do AgroLog:

- evento ou publicacao capturada: `observado`;
- impacto potencial sobre shipping, energia, fertilizantes etc.: `inferido`;
- estimativas quantitativas futuras: `estimado` quando aplicavel.

## Fontes do MVP

### GDELT DOC 2.0

Status: habilitado no arquivo de exemplo.

Uso: radar OSINT/noticioso de alta frequencia. O coletor consulta uma janela recente e armazena o JSON bruto antes de normalizar artigos como `osint_signal`.

Limite metodologico: GDELT e um sistema de monitoramento de midia. Uma materia retornada pelo GDELT nao prova que o evento descrito ocorreu conforme publicado.

### UCDP GED Candidate

Status: preparado, mas desabilitado por padrao.

Uso pretendido: camada de eventos de violencia organizada codificados por pesquisadores, com localizacao, atores, tipo de violencia e estimativas de fatalidades quando disponiveis.

A API atual exige token em header `x-ucdp-access-token`. O token deve ficar em `UCDP_API_TOKEN` no ambiente e nunca no GitHub.

O exemplo esta fixado na versao Candidate `26.0.7` observada em 24/08/2026 para reproducibilidade. Antes de producao, o coletor deve ganhar:

1. descoberta/atualizacao controlada da versao Candidate vigente;
2. janela temporal dinamica usando `StartDate`/`EndDate`;
3. paginacao completa seguindo `TotalPages`/`NextPageUrl`;
4. controle da cota da API;
5. armazenamento point-in-time de cada versao consultada.

### Fontes planejadas apos o MVP

- ACLED: eventos politicos/conflitos, condicionado a credenciais, licenca e termos vigentes;
- ReliefWeb/OCHA: relatorios humanitarios curados, condicionado a appname aprovado;
- NASA FIRMS: anomalias termicas como sinal contextual, nunca como prova autonoma de ataque;
- GDACS: desastres naturais que possam convergir com crises geopoliticas/logisticas;
- ADS-B/OpenSky: atividade aerea publica agregada, tratada como sinal contextual;
- AIS: atividade maritima publica/autorizada, integrada ao piloto AIS ja previsto no AgroLog;
- RSS de fontes primarias e imprensa homologada;
- mercados de previsao ja previstos na arquitetura, sempre como expectativa observada e nao como fato futuro.

## Evento normalizado

O contrato inicial e `GeopoliticalEvent` em `collector/geopolitical.py`.

Campos centrais:

- `event_id` — hash estavel do evento na fonte;
- `source_id`;
- `source_event_id`;
- `title`;
- `event_type`;
- `data_referencia`;
- `data_publicacao`;
- `data_coleta`;
- `verification_level`;
- `evidence_class`;
- `country` / `region` quando sustentados pela fonte;
- `latitude` / `longitude` quando sustentadas pela fonte;
- `fatalities_best` quando fornecido pela base codificada;
- `actors`;
- `source_url`;
- `raw_artifact_ref`;
- `impact_areas`;
- `impact_evidence_class = inferido`.

O parser do GDELT nao usa o pais de origem do veiculo de imprensa como local do evento. Localizacao so deve ser preenchida quando houver evidencia apropriada.

## Inferencia de impacto AgroLog

O MVP aplica uma taxonomia conservadora de palavras-chave para marcar possivel relacao causal com:

- `energy`;
- `fertilizers`;
- `shipping`;
- `trade`;
- `fx`;
- `agriculture`;
- `logistics`.

Essa marcacao e sempre `inferido`. Ela serve para triagem, nao para concluir impacto economico.

Exemplo conceitual:

```text
ataque / bloqueio em porto
        |
        +--> shipping [inferido]
        +--> logistics [inferido]
        |
        v
analise posterior de rota, volume, produto e alternativa logistica
        |
        v
impacto AgroLog validado ou descartado
```

## Deduplicacao e corroboracao

O MVP agrupa eventos quando:

- estao no mesmo dia de referencia;
- o pais coincide quando ambos possuem pais conhecido;
- a similaridade Jaccard dos titulos supera o limite configurado.

O agrupamento preserva os IDs dos membros e conta fontes distintas. Ele nao apaga a evidencia original.

Fases seguintes devem acrescentar:

- entity resolution de atores e locais;
- distancia geoespacial;
- janela temporal mais granular;
- similaridade semantica;
- identificadores canonicos de conflito;
- relacao entre noticia, evento UCDP/ACLED e sinal fisico.

## Score de prioridade

`score_cluster()` produz um numero de 0 a 100 para ordenar a fila de analise. Nao representa probabilidade nem nivel oficial de ameaca.

Versao inicial: `geo-watch-v0.1`.

Componentes:

- peso por nivel de verificacao;
- fatalidades quando fornecidas por base codificada;
- quantidade de fontes independentes no cluster;
- presenca de termo de escalada;
- existencia de impacto AgroLog potencial.

Qualquer mudanca nos pesos deve gerar nova versao do metodo e ser validada historicamente antes de uso em alertas de alta criticidade.

## Execucao local do MVP

Sem token UCDP, o GDELT pode ser executado sozinho:

```bash
python scripts/run_geopolitical_watch.py
```

Para alterar a raiz local:

```bash
python scripts/run_geopolitical_watch.py --root .agrolog
```

Para uma fonte especifica:

```bash
python scripts/run_geopolitical_watch.py --source gdelt_conflict_watch
```

Quando houver token UCDP:

```bash
export UCDP_API_TOKEN="..."
```

Depois, habilitar a fonte UCDP somente apos implementar paginacao/janela dinamica e revisar a versao Candidate vigente.

## Saidas do MVP

O runner escreve:

```text
.agrolog/
  raw/
  manifests/
  state/
  normalized/
    geopolitical/
      <source_id>/YYYY-MM-DD/<sha>.jsonl
      latest_clusters.jsonl
```

Nenhum RAW ou segredo deve ser commitado.

## Regras para alertas futuros

Um alerta operacional do AgroLog nao deve disparar apenas porque uma manchete contem palavras de guerra.

Requisitos recomendados por nivel:

### Informativo

Um sinal OSINT relevante, claramente rotulado como nao corroborado.

### Relevante

Corroboracao por mais de uma fonte ou evento codificado/curado, com caminho causal plausivel para variavel AgroLog.

### Critico

Convergencia de fontes independentes mais evidencia de impacto material potencial, por exemplo interrupcao de estreito, porto, terminal, oleoduto, rota maritima ou fluxo comercial relevante.

Alertas criticos devem incluir:

- o que aconteceu;
- o que esta confirmado e o que ainda e sinal;
- fontes;
- data/hora;
- local;
- caminho causal para AgroLog;
- variaveis potencialmente afetadas;
- cenarios alternativos;
- confianca;
- o que deve ser observado a seguir.

## Integracao com o AgroLog MT

O modulo nao deve criar um boletim geopolitico separado por padrao. O evento entra no produto principal apenas quando houver relevancia causal para agricultura/logistica.

Exemplos de caminhos que justificam promocao:

- conflito -> petroleo -> diesel -> custo rodoviario;
- conflito -> gas/amonia/potassio -> fertilizantes -> custo de producao;
- conflito -> Mar Vermelho/Suez/Hormuz -> shipping -> frete maritimo/tempo de viagem;
- conflito -> Mar Negro -> trigo/milho/oleos vegetais -> precos e substituicao de fluxo;
- sancoes/bloqueio -> comercio -> cambio/prêmios/rotas;
- ataque a infraestrutura -> porto/ferrovia/canal -> gargalo logistico.

Sem esse elo, o evento permanece no Geopolitical Watch e nao polui os relatorios AgroLog.

## Referencias de arquitetura open source

Os projetos abaixo sao benchmarks, nao dependencias obrigatorias:

- `studioblvck/world-monitor` — dashboard global, multiplas camadas, fusao de sinais e convergencia;
- `aryarajsingh/OSINT-WarRoom` — arquitetura simples self-hosted, classificacao, deduplicacao e alertas.

O AgroLog deve reaproveitar conceitos, nao copiar plataforma inteira. Componentes externos so entram apos revisao de licenca, seguranca, manutencao, termos e estrategia de saida.

## Estado atual do MVP

Implementado nesta primeira iteracao:

- adaptador HTTP com segredo carregado por variavel de ambiente;
- configuracao GDELT pronta;
- configuracao UCDP preparada e desabilitada;
- parser/normalizador GDELT;
- parser/normalizador UCDP;
- IDs estaveis;
- classificacao da evidencia;
- inferencia de areas de impacto AgroLog;
- clustering/deduplicacao inicial;
- score de prioridade versionado;
- runner local;
- testes unitarios sem dados reais.

Nao implementado ainda:

- persistencia BigQuery;
- paginacao UCDP;
- janela temporal dinamica UCDP;
- ACLED;
- ReliefWeb;
- NASA FIRMS;
- AIS/ADS-B nesta camada;
- dashboard/mapa;
- alertas automatizados;
- grafo causal e avaliacao historica do score.

Esses itens devem avancar como extensao incremental do modulo, sem criar uma segunda fonte de verdade e sem ultrapassar os gates P0/P1 do nucleo atual.
